class_name ReplayRecorder
extends Node


# Records gameplay actions and state to replay files.
# Creates action log (.jsonl) and periodic checksum snapshots (.json).


# Checkpoint frequency: every N seconds of gameplay at 30 ticks/sec
const CHECKPOINT_INTERVAL_SECONDS: int = 10
const TICKS_PER_SECOND: int = 30


var _metadata: ReplayMetadata
var _replay_file: FileAccess = null
var _is_recording: bool = false
var _last_checkpoint_tick: int = 0
var _checkpoint_interval_ticks: int


#########################
###     Built-in      ###
#########################

func _ready():
	_checkpoint_interval_ticks = CHECKPOINT_INTERVAL_SECONDS * TICKS_PER_SECOND


#########################
###       Public      ###
#########################

# Start recording a new replay
func start_recording(metadata: ReplayMetadata) -> bool:
	if _is_recording:
		push_error("ReplayRecorder: Already recording")
		return false
	
	_metadata = metadata
	_metadata.timestamp = Time.get_unix_time_from_system()
	_metadata.game_version = ProjectSettings.get_setting("application/config/version", "unknown")
	_metadata.replay_id = ReplayMetadata.generate_replay_id(_metadata)
	
	# Ensure replay directories exist
	_ensure_replay_directories()
	
	# Open replay file for writing
	var replay_path: String = _get_replay_path(_metadata.replay_id)
	_replay_file = FileAccess.open(replay_path, FileAccess.WRITE)
	
	if _replay_file == null:
		push_error("ReplayRecorder: Failed to create replay file: ", replay_path)
		return false
	
	# Write metadata as first line
	_write_metadata_line()
	
	_is_recording = true
	_last_checkpoint_tick = 0
	
	print("ReplayRecorder: Started recording to ", replay_path)
	return true


# Record actions from a timeslot
func record_timeslot(tick: int, actions: Array):
	if !_is_recording:
		return
	
	for action in actions:
		_write_action_line(tick, action)
	
	# Check if we need to create a checkpoint
	if tick - _last_checkpoint_tick >= _checkpoint_interval_ticks:
		_create_checkpoint(tick)
		_last_checkpoint_tick = tick


# Stop recording and finalize the replay file
func stop_recording(final_tick: int):
	if !_is_recording:
		return
	
	_metadata.total_ticks = final_tick
	
	# Create final checkpoint if needed
	if final_tick > _last_checkpoint_tick:
		_create_checkpoint(final_tick)
	
	if _replay_file != null:
		_replay_file.close()
		_replay_file = null
	
	print("ReplayRecorder: Stopped recording. Total ticks: ", final_tick)
	_is_recording = false


# Get the current replay ID
func get_replay_id() -> String:
	return _metadata.replay_id if _metadata != null else ""


# Get the current metadata
func get_metadata() -> ReplayMetadata:
	return _metadata


# Check if currently recording
func is_recording() -> bool:
	return _is_recording


#########################
###      Private      ###
#########################

func _ensure_replay_directories():
	var dir: DirAccess = DirAccess.open("user://")
	if dir == null:
		push_error("ReplayRecorder: Failed to open user:// directory")
		return
	
	if !dir.dir_exists("replays"):
		dir.make_dir("replays")
	
	if !dir.dir_exists("replays/_state"):
		dir.make_dir("replays/_state")


func _get_replay_path(replay_id: String) -> String:
	return "user://replays/%s.jsonl" % replay_id


func _get_checkpoint_path(replay_id: String, tick: int) -> String:
	return "user://replays/_state/%s-%d.json" % [replay_id, tick]


func _write_metadata_line():
	var metadata_dict: Dictionary = _metadata.to_dict()
	var line: Dictionary = {
		"type": "metadata",
		"data": metadata_dict
	}
	
	var json_string: String = JSON.stringify(line)
	_replay_file.store_line(json_string)
	_replay_file.flush()


func _write_action_line(tick: int, action: Dictionary):
	var line: Dictionary = {
		"tick": tick,
		"type": "action",
		"data": action
	}
	
	var json_string: String = JSON.stringify(line)
	_replay_file.store_line(json_string)
	_replay_file.flush()


func _create_checkpoint(tick: int):
	print("ReplayRecorder: Creating checkpoint at tick ", tick)
	
	# Build checksum tree
	var checksum_tree: Dictionary = ChecksumBuilder.build_checksum_tree(tick)
	
	# Save to file
	var checkpoint_path: String = _get_checkpoint_path(_metadata.replay_id, tick)
	var file: FileAccess = FileAccess.open(checkpoint_path, FileAccess.WRITE)
	
	if file == null:
		push_error("ReplayRecorder: Failed to create checkpoint file: ", checkpoint_path)
		return
	
	var json_string: String = JSON.stringify(checksum_tree, "\t")
	file.store_string(json_string)
	file.close()
	
	# Add checkpoint tick to metadata
	_metadata.checkpoint_ticks.append(tick)
	
	# Write checkpoint reference to replay file
	var checkpoint_line: Dictionary = {
		"tick": tick,
		"type": "checkpoint",
		"file": "%s-%d.json" % [_metadata.replay_id, tick]
	}
	
	var json_line: String = JSON.stringify(checkpoint_line)
	_replay_file.store_line(json_line)
	_replay_file.flush()

