# Replay System v1

- Goal: log single-player actions deterministically, allow scenario replay from user://replays, and keep architecture ready for multiplayer and deeper verification later.
- Scope: Godot action logging, checkpoint checksums, Create Game replay selection, pause-menu export button, playback lockout until log ends.

## Key Requirements

- Store logs in user://replays/<id>.jsonl; checkpoints in user://replays/_state/<id>-<tick>.json with SHA-256 hashes.
- Only host-side (single-player) capture for now, but design modules so multiplayer host can be swapped in.
- Replay selection lives in Create Game; once a replay is chosen, other settings are disabled and metadata from the log drives scenario setup.
- Game resumes normal input after log finishes; player can change speed during playback if determinism holds.
- Pause menu exposes Save Replay button writing full history from tick 0 to current time.
- Do not compress outputs; keep runtime overhead low enough for normal and 3x speed; accept minor cost at extreme speeds.

## Architecture Overview

- ReplayService (autoload singleton)
	- Manages session metadata, file handles, and tick bookkeeping.
	- Provides host hooks: begin_session(seed, map, options), record_action(tick, action_dict), emit_checkpoint(tick, checksum_payload).
	- Handles rollover when player triggers save from pause menu.
	- Exposes ReplaySessionDescriptor to UI for listing stored replays.
- ChecksumBuilder utility
	- Traverses state snapshots at configurable period (default derived from GameClient.CHECKSUM_PERIOD_TICKS).
	- Produces deterministic dictionaries for each entity (player, tower, creep, projectile, timers, items).
	- Generates SHA-256 per node and aggregates per-tree checksums for incremental verification.
	- Frequency remains adjustable via project setting.
- ReplayPlaybackController
	- Injected when lobby selects a replay; feeds stored timeslots to GameClient in lieu of live host.
	- Locks player input by suppressing GameClient.add_action until playback complete.
	- Supports speed adjustments by controlling timeslot dispatch cadence, assuming tick order remains unchanged.
	- On completion, re-enables input and stops artificial timeslot supply.
- UI Integrations
	- Create Game menu: file picker (limited to jsonl); shows metadata summary; disables manual settings toggles while replay is selected.
	- Pause menu: Save Replay button invoking ReplayService.flush_snapshot().

## Data Formats

- meta header (first line of jsonl or a companion json) with keys: version, replay_id, seed, map_id, difficulty, modifiers, player loadout (exp password hash, wisdom upgrades snapshot), created_at.
- Each action entry: { "tick": int, "player_id": int, "type": string, "fields": dictionary, "checksum_ref": optional state file name }.
- Checkpoint file: { "tick": int, "hash": string, "entities": { "player:<id>": { "hash": string, "children": ... } } }.
- Maintain deterministic key ordering by assembling arrays before hashing.

## Determinism Notes

- Verify existing RNG usage in GameHost/GameClient; capture initial seeds per RandomNumberGenerator instance.
- Assume speed multipliers only affect render pacing; confirm GameClient uses fixed physics delta so we do not log speed changes.
- If future findings show speed influences logic, extend log schema with mode changes.

## Multiplayer Readiness

- ReplayService designed so record_action can accept player_id from any peer; internal storage neutral to count.
- Placeholder hook for host-only capture ensures upgrade path once multiplayer logging is enabled.
- ChecksumBuilder should support merging multiple player subtrees without schema changes.

## Implementation Phases

1. Add ReplayService and minimal configuration; hook host to log and flush metadata.
2. Build checksum traversal for core entities and scheduled dumping.
3. Implement Create Game replay selection and playback controller, including input lock and resume.
4. Wire pause menu save button to ReplayService.
5. Add soft verification reporting comparing live state to stored checksums during playback.

## Open Points

- Confirm preferred replay id scheme (timestamp, uuid, or deterministic seed-based).
- Determine exact UI layout for disabled settings after replay selection.
- Need guidance on how to surface verification mismatches (chat, console, popup) beyond baseline logging.
