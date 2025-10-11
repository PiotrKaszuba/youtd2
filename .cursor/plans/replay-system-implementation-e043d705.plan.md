<!-- e043d705-47e4-4cfe-b7c8-388e6e00fdc1 0967559f-9873-445f-b962-a74782b7b4f5 -->
# Replay System Implementation

## Overview

Implement deterministic replay recording/playback for singleplayer with action logging to `.jsonl` files, periodic state checksums, and full replay controls. Architecture designed for easy multiplayer extension.

## Core Architecture

### 1. Replay File Structure

- **Action log**: `user://replays/<replay_id>.jsonl` - one action per line with tick and metadata
- **State checksum snapshots**: `user://replays/_state/<replay_id>-<tick>.json` - hierarchical checksums
- **Replay ID**: SHA-256 hash of initial game state + timestamp
- Format: JSONL (JSON Lines) for streaming and easy debugging

### 2. Key Components to Create

**`src/replay/replay_recorder.gd`** - Records gameplay

- Captures all executed actions from timeslots
- Stores initial game state (seed, difficulty, mode, exp password, wisdom upgrades, builder)
- Writes actions to `.jsonl` incrementally
- Generates periodic hierarchical checksums (every 30 * TURN_LENGTH * N ticks, N=10 default)
- Uses FileAccess in append mode for performance

**`src/replay/replay_player.gd`** - Plays back replays

- Reads replay metadata and action log
- Injects actions into game at recorded ticks
- Locks player input during playback (except speed/pause controls)
- Allows speed changes (1x, 3x, 9x)
- Transitions to normal play when replay ends

**`src/replay/replay_state_verifier.gd`** - Verifies determinism

- Generates hierarchical checksums matching recorder format
- Compares against saved snapshots at checkpoints
- On mismatch: walks checksum tree to find divergent entities
- Reports differences to console and chat with entity paths

**`src/replay/checksum_builder.gd`** - Hierarchical checksum generation

- Root: overall game state hash
- Level 1: per-player state (gold, tomes, damage, level, lives)
- Level 2: per-entity-type (all towers, all creeps, all items)
- Level 3: individual entities with identifying info (tower ID+position, creep UID+position, item UID)
- Entity state: relevant fields (HP, exp, damage dealt, position, etc.)
- Returns tree structure with human-readable paths

**`src/replay/replay_metadata.gd`** - Replay metadata structure

- Initial state: origin_seed, difficulty, game_mode, wave_count, team_mode, player_mode
- Player data: exp_password, wisdom_upgrades, builder_id
- Checksum snapshot ticks
- Game version/timestamp
- Helper methods for serialization

### 3. UI Changes

**`src/ui/title_screen/configure_singleplayer_menu.gd`** - Add replay selection

- Add "Load Replay" file picker button
- When replay selected: grey out other settings, load settings from replay
- Store "before_replay_exp_password" in Settings temporarily
- Pass replay file path through Globals to GameScene

**`src/ui/game_menu/game_menu.gd`** - Add "Save Replay" button

- Button visible only during actual gameplay (not during replay playback)
- Triggers replay save from game start to current tick
- Shows file saved message

**`src/ui/hud/replay_controls.gd/tscn`** - Replay playback controls (new)

- Speed buttons (1x, 3x, 9x)
- Pause/resume
- Progress indicator showing current/total ticks
- Only visible during replay playback

### 4. Integration Points

**`src/game_scene/game_scene.gd`** - Main integration

- Check if loading replay via Globals
- If replay: initialize ReplayPlayer, disable ReplayRecorder
- If normal game: initialize ReplayRecorder
- Restore exp password after replay if needed

**`src/game_scene/game_client.gd`** - Action capture

- In `_do_tick()` after executing timeslot: notify ReplayRecorder of actions + tick
- For replay: inject actions from ReplayPlayer before execution
- Call ReplayStateVerifier at checkpoint ticks

**`src/singletons/globals.gd`** - Add replay state

- `_replay_file_path: String = ""`
- `_is_replaying: bool = false`
- `_replay_recorder: ReplayRecorder = null`
- Getters/setters

## Implementation Details

### Action Logging Format (JSONL)

```json
{"type": "metadata", "data": {...initial_state...}}
{"tick": 0, "type": "action", "data": {...action_dict...}}
{"tick": 15, "type": "action", "data": {...action_dict...}}
{"tick": 900, "type": "checkpoint", "file": "replay_id-900.json"}
```

### Checksum Snapshot Format (JSON)

```json
{
  "tick": 900,
  "checksum": "abc123...",
  "children": {
    "player_0": {
      "checksum": "def456...",
      "path": "player_0",
      "data": {"gold": 1000, "tomes": 5, ...},
      "children": {
        "towers": {
          "checksum": "ghi789...",
          "path": "player_0/towers",
          "children": {
            "tower_0_32x48": {...},
            ...
          }
        },
        "items": {...},
        ...
      }
    },
    "creeps": {...},
    ...
  }
}
```

### Determinism Considerations

1. **UID generation**: Uses static counter, deterministic if creation order same
2. **RNG**: Already uses `Globals.synced_rng` with stored seed
3. **Tick timing**: Fixed tick delta, game speed doesn't affect logic
4. **Action order**: Actions replayed at exact ticks from timeslots
5. **Float precision**: Use `floori()` for checksum values where appropriate

### Potential Issues & Solutions

**Problem**: Actions with object references

- **Solution**: Already using UIDs in action serialization (tower_id, uid, uid_2, etc.)
- Verify all actions use UID not direct references

**Problem**: Complex action parameters (positions, arrays)

- **Solution**: Action.serialize() already handles Vector2 and Arrays in Dictionary
- Test edge cases during implementation

**Problem**: Tick synchronization

- **Solution**: Store tick number with each action, inject at exact tick in replay

**Problem**: Initial state restoration

- **Solution**: Store complete initial state in metadata, restore before replay starts
- Backup player exp password to temporary setting

**Problem**: UID determinism

- **Solution**: Since actions replay at same ticks, object creation order should match
- Verify by comparing checksums

**Problem**: Performance of detailed checksums

- **Solution**: Adjustable checkpoint frequency (default: every 10 seconds of gameplay)
- Skip non-critical entities if needed

## Testing Strategy

1. Record short (5 min) singleplayer game
2. Replay and verify checksums match at all checkpoints
3. Test replay speed changes (1x, 3x, 9x)
4. Test continuing gameplay after replay
5. Test exp password backup/restore
6. Intentionally break determinism and verify detection

## Multiplayer Extension Path

- ReplayRecorder already captures player_id in actions
- For multiplayer: only host records, captures all players' actions
- Replay metadata includes player count and peer IDs
- ReplayPlayer creates multiple Player instances
- State verifier checksums all players

### To-dos

- [ ] Create core replay classes: ReplayRecorder, ReplayPlayer, ReplayMetadata, ChecksumBuilder, ReplayStateVerifier
- [ ] Implement hierarchical checksum generation with per-entity details
- [ ] Implement ReplayRecorder: action logging, metadata storage, checkpoint generation
- [ ] Implement ReplayPlayer: action injection, input locking, speed control
- [ ] Implement ReplayStateVerifier: checksum comparison and diff reporting
- [ ] Integrate replay recording/playback into GameClient tick loop
- [ ] Add replay file selection to ConfigureSinglePlayerMenu with setting override
- [ ] Add 'Save Replay' button to game menu pause screen
- [ ] Create replay controls UI (speed, progress) shown during playback
- [ ] Integrate replay system into GameScene initialization and setup
- [ ] Test recording, playback, verification, and continuation of singleplayer games