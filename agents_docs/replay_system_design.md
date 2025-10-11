# Replay System Design Document

## Overview

This document outlines the design for a comprehensive replay system for the tower defense game, including action logging, state verification, and replay functionality.

## Current System Analysis

### Action System
- **Action Class**: Central wrapper for all user actions with serialization support
- **Action Types**: 25+ different action types (build tower, upgrade, chat, etc.)
- **Execution Flow**: Actions are sent to host, compiled into timeslots, then executed on all clients
- **Serialization**: Actions already support Dictionary serialization for RPC

### Multiplayer Synchronization
- **Tick-based**: 30 ticks per second with deterministic execution
- **Timeslots**: Actions grouped by tick intervals (3 ticks for multiplayer, 1 for singleplayer)
- **Checksums**: Basic MD5 checksums every 90 ticks for desync detection
- **Current State**: Limited checksum verification (player stats only)

### Game State Structure
- **Entities**: Towers, Creeps, Projectiles, Items, Players
- **Managers**: PlayerManager, GroupManager, various singleton systems
- **Deterministic RNG**: `synced_rng` for multiplayer-safe random operations
- **Game Speed**: Configurable update ticks per physics tick

## Replay System Architecture

### 1. Action Logging System

#### ReplayLogger Class
```gdscript
class_name ReplayLogger extends Node

var _action_log: Array[Dictionary] = []
var _initial_state: Dictionary = {}
var _checksum_dumps: Dictionary = {}  # {tick -> checksum_file_path}
var _is_logging: bool = false
var _replay_file_path: String = ""

func start_logging(file_path: String):
	_is_logging = true
	_replay_file_path = file_path
	_capture_initial_state()
	
func log_action(action: Dictionary, tick: int):
	if !_is_logging:
		return
		
	var log_entry = {
		"tick": tick,
		"action": action,
		"timestamp": Time.get_ticks_msec()
	}
	_action_log.append(log_entry)
	
func save_replay():
	var replay_data = {
		"version": "1.0",
		"initial_state": _initial_state,
		"actions": _action_log,
		"checksum_dumps": _checksum_dumps,
		"game_settings": _capture_game_settings()
	}
	
	var file = FileAccess.open(_replay_file_path, FileAccess.WRITE)
	file.store_string(JSON.stringify(replay_data))
	file.close()
```

#### Integration Points
- **GameHost**: Log actions when they're received and processed
- **GameClient**: Log actions when they're executed
- **Action System**: Add logging hooks to action execution

### 2. Comprehensive State Verification

#### StateVerifier Class
```gdscript
class_name StateVerifier extends Node

func calculate_comprehensive_checksum() -> Dictionary:
	var state_tree = {
		"players": _calculate_player_checksums(),
		"towers": _calculate_tower_checksums(),
		"creeps": _calculate_creep_checksums(),
		"projectiles": _calculate_projectile_checksums(),
		"items": _calculate_item_checksums(),
		"game_time": _calculate_game_time_checksum(),
		"rng_state": _calculate_rng_checksum()
	}
	
	return state_tree

func _calculate_tower_checksums() -> Dictionary:
	var tower_checksums = {}
	var tower_list = Utils.get_tower_list()
	
	for tower in tower_list:
		var tower_id = _get_tower_identifier(tower)
		tower_checksums[tower_id] = {
			"checksum": _calculate_tower_state_checksum(tower),
			"name": tower.get_display_name(),
			"position": tower.get_position_wc3(),
			"player_id": tower.get_player().get_id()
		}
		
	return tower_checksums

func _calculate_tower_state_checksum(tower: Tower) -> String:
	var ctx = HashingContext.new()
	ctx.start(HashingContext.HASH_MD5)
	
	# Include all relevant tower state
	var state_data = PackedByteArray()
	state_data.append_array(_float_to_bytes(tower.get_level()))
	state_data.append_array(_float_to_bytes(tower.get_experience()))
	state_data.append_array(_float_to_bytes(tower.get_health()))
	state_data.append_array(_float_to_bytes(tower.get_mana()))
	state_data.append_array(_float_to_bytes(tower.get_attack_damage_dealt()))
	state_data.append_array(_float_to_bytes(tower.get_spell_damage_dealt()))
	state_data.append_array(_int_to_bytes(tower.get_kill_count()))
	state_data.append_array(_int_to_bytes(tower.get_uid()))
	
	ctx.update(state_data)
	return ctx.finish().hex_encode()
```

#### Periodic State Dumps
- **Frequency**: Every 300 ticks (10 seconds at 30fps)
- **Storage**: Separate checksum files with tick-based naming
- **Structure**: Hierarchical checksum tree for granular verification

### 3. Replay Execution System

#### ReplayPlayer Class
```gdscript
class_name ReplayPlayer extends Node

var _replay_data: Dictionary = {}
var _current_action_index: int = 0
var _is_playing: bool = false
var _playback_speed: float = 1.0
var _target_tick: int = 0
var _action_queue: Array[Dictionary] = []

func load_replay(file_path: String) -> bool:
	var file = FileAccess.open(file_path, FileAccess.READ)
	if file == null:
		return false
		
	var json_string = file.get_as_text()
	file.close()
	
	_replay_data = JSON.parse_string(json_string)
	return _replay_data != null

func start_replay():
	_restore_initial_state()
	_is_playing = true
	_target_tick = 0
	
func _execute_replay_tick(tick: int):
	# Execute all actions for this tick
	while _current_action_index < _replay_data.actions.size():
		var action_entry = _replay_data.actions[_current_action_index]
		if action_entry.tick > tick:
			break
			
		if action_entry.tick == tick:
			_execute_replay_action(action_entry.action)
			
		_current_action_index += 1
```

#### Replay Integration
- **GameClient**: Override action execution during replay
- **UI**: Replay controls (play, pause, speed, seek)
- **State Restoration**: Load initial state and apply actions

### 4. Complex Object Serialization

#### Problematic Cases Identified
1. **Tower References**: Towers have UIDs that change between sessions
2. **Item References**: Items have UIDs and complex state
3. **Position References**: Vector3 positions need precise serialization
4. **Player References**: Player IDs may differ between sessions

#### Solutions

##### Reference Resolution System
```gdscript
class_name ReferenceResolver extends Node

var _uid_mapping: Dictionary = {}  # {old_uid -> new_uid}
var _player_mapping: Dictionary = {}  # {old_player_id -> new_player_id}

func resolve_tower_reference(old_uid: int) -> Tower:
	var new_uid = _uid_mapping.get(old_uid, -1)
	if new_uid == -1:
		push_error("Failed to resolve tower reference: " + str(old_uid))
		return null
		
	return GroupManager.get_by_uid("towers", new_uid) as Tower

func resolve_item_reference(old_uid: int) -> Item:
	var new_uid = _uid_mapping.get(old_uid, -1)
	if new_uid == -1:
		push_error("Failed to resolve item reference: " + str(old_uid))
		return null
		
	return GroupManager.get_by_uid("items", new_uid) as Item
```

##### Action Serialization Enhancement
```gdscript
# Enhanced action serialization for replay
func serialize_for_replay() -> Dictionary:
	var serialized = _data.duplicate()
	
	# Convert references to stable identifiers
	if serialized.has(Action.Field.TOWER_ID):
		var tower = GroupManager.get_by_uid("towers", serialized[Action.Field.TOWER_ID])
		if tower:
			serialized[Action.Field.TOWER_ID] = _get_tower_identifier(tower)
			
	return serialized

func _get_tower_identifier(tower: Tower) -> String:
	return str(tower.get_player().get_id()) + "_" + str(tower.get_position_wc3())
```

### 5. Tick Synchronization Solutions

#### Deterministic Execution
- **RNG State**: Capture and restore `synced_rng` state
- **Action Ordering**: Maintain strict action execution order
- **Timing Independence**: Replay speed doesn't affect game logic

#### Replay Speed Control
```gdscript
class_name ReplaySpeedController extends Node

var _base_tick_rate: int = 30
var _current_speed: float = 1.0

func set_replay_speed(speed: float):
	_current_speed = speed
	Globals.set_update_ticks_per_physics_tick(int(_base_tick_rate * speed))

func pause_replay():
	Globals.set_update_ticks_per_physics_tick(0)

func resume_replay():
	Globals.set_update_ticks_per_physics_tick(int(_base_tick_rate * _current_speed))
```

### 6. UI Integration

#### Replay Controls
- **Play/Pause**: Toggle replay execution
- **Speed Control**: 0.25x, 0.5x, 1x, 2x, 4x speeds
- **Seek**: Jump to specific tick or time
- **Save Replay**: Save current game state as replay

#### Replay Menu
- **Load Replay**: File browser for replay selection
- **Replay Settings**: Speed, auto-pause options
- **Verification**: Show checksum verification results

### 7. File Format Specification

#### Replay File Structure
```json
{
	"version": "1.0",
	"metadata": {
		"game_version": "1.0.0",
		"created_at": "2024-01-01T00:00:00Z",
		"duration_ticks": 18000,
		"player_count": 2
	},
	"initial_state": {
		"game_settings": {...},
		"player_states": {...},
		"map_state": {...},
		"rng_seed": 12345
	},
	"actions": [
		{
			"tick": 0,
			"action": {...},
			"timestamp": 1640995200000
		}
	],
	"checksum_dumps": {
		"300": "checksums/state_300.json",
		"600": "checksums/state_600.json"
	}
}
```

#### Checksum File Structure
```json
{
	"tick": 300,
	"timestamp": 1640995200000,
	"root_checksum": "abc123...",
	"state_tree": {
		"players": {...},
		"towers": {...},
		"creeps": {...}
	}
}
```

## Implementation Plan

### Phase 1: Core Logging System
1. Implement ReplayLogger class
2. Add logging hooks to GameHost and GameClient
3. Create basic replay file format
4. Implement action serialization

### Phase 2: State Verification
1. Implement StateVerifier class
2. Create comprehensive checksum calculation
3. Add periodic state dumps
4. Implement verification system

### Phase 3: Replay Execution
1. Implement ReplayPlayer class
2. Add reference resolution system
3. Create replay controls UI
4. Implement state restoration

### Phase 4: Advanced Features
1. Add replay speed control
2. Implement seek functionality
3. Add verification UI
4. Create replay management system

## Additional Considerations

### Multiplayer Replay
- **Host Authority**: Only host actions are logged for multiplayer
- **Desync Handling**: Replay system can detect and report desyncs
- **Player Perspective**: Replay shows host's perspective of the game

### Performance Optimization
- **Compression**: Use gzip compression for replay files
- **Incremental Saves**: Save replay data incrementally
- **Memory Management**: Stream large replay files

### Error Handling
- **Corruption Detection**: Verify replay file integrity
- **Recovery**: Attempt to recover from partial corruption
- **Fallback**: Graceful degradation for unsupported features

## Requirements Clarification

### Storage and File Format
- **Replay Files**: `user://replays/<id>.jsonl` (JSON Lines format)
- **State Dumps**: `user://replays/_state/<id>-<tick>.json` (SHA-256 checksums)
- **No Compression**: Keep files uncompressed for now
- **No File Size Limits**: Start with simple examples

### Scope and Compatibility
- **Single-player Only**: Start with deterministic single-player replays
- **Multiplayer Later**: Plan architecture for easy multiplayer extension
- **Host Authority**: In multiplayer, only host saves all players' actions
- **Create Game Integration**: Load replay option in "Create Game" menu
- **Settings Override**: Replay settings take precedence, grey out other options

### Performance and Determinism
- **Game Speed**: Assume game speed changes don't affect determinism
- **Performance Impact**: Minimal impact on normal/3x speed, acceptable on 9x speed
- **Checksum Frequency**: Adjustable frequency, lower by default
- **Granularity**: Detailed per-entity checksums (towers/creeps/items)

### User Experience
- **Pause Screen**: Save current replay option on pause screen
- **Replay End**: Player regains full control when replay ends
- **Continue Playing**: Player can continue after replay ends
- **Simple Start**: No additional features initially

## Conclusion

This design provides a focused replay system for single-player games with clear extension points for multiplayer. The architecture supports incremental implementation while maintaining performance and determinism.
