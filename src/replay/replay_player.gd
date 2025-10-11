class_name ReplayPlayer
extends Node


# Plays back recorded replays by injecting actions at the correct ticks.
# Manages input locking and replay controls.


signal replay_finished()
signal replay_progress_updated(current_tick: int, total_ticks: int)


var _metadata: ReplayMetadata
var _actions_by_tick: Dictionary = {}  # {tick -> [actions]}
var _is_playing: bool = false
var _current_tick: int = 0
var _replay_finished: bool = false


#########################
###       Public      ###
#########################

# Load and prepare a replay for playback
func load_replay(replay_path: String) -> bool:
	if !FileAccess.file_exists(replay_path):
		push_error("ReplayPlayer: Replay file not found: ", replay_path)
		return false
	
	var file: FileAccess = FileAccess.open(replay_path, FileAccess.READ)
	if file == null:
		push_error("ReplayPlayer: Failed to open replay file: ", replay_path)
		return false
	
	_actions_by_tick.clear()
	_metadata = null
	_current_tick = 0
	_replay_finished = false
	
	# Read and parse JSONL file
	while !file.eof_reached():
		var line: String = file.get_line().strip_edges()
		if line.is_empty():
			continue
		
		var json: JSON = JSON.new()
		var parse_result: Error = json.parse(line)
		if parse_result != OK:
			push_error("ReplayPlayer: Failed to parse replay line: ", line)
			continue
		
		var entry: Dictionary = json.data
		var entry_type: String = entry.get("type", "")
		
		if entry_type == "metadata":
			_metadata = ReplayMetadata.from_dict(entry.get("data", {}))
		elif entry_type == "action":
			var tick: int = entry.get("tick", 0)
			var action: Dictionary = entry.get("data", {})
			
			if !_actions_by_tick.has(tick):
				_actions_by_tick[tick] = []
			
			_actions_by_tick[tick].append(action)
		elif entry_type == "checkpoint":
			# Checkpoint entries are just for reference, we don't need to load them here
			pass
	
	file.close()
	
	if _metadata == null:
		push_error("ReplayPlayer: No metadata found in replay file")
		return false
	
	print("ReplayPlayer: Loaded replay with %d actions, total ticks: %d" % [_count_total_actions(), _metadata.total_ticks])
	return true


# Get metadata from loaded replay
func get_metadata() -> ReplayMetadata:
	return _metadata


# Start replay playback
func start_playback():
	_is_playing = true
	_current_tick = 0
	_replay_finished = false
	print("ReplayPlayer: Started playback")


# Stop replay playback
func stop_playback():
	_is_playing = false
	print("ReplayPlayer: Stopped playback")


# Get actions for a specific tick (to be injected into game)
func get_actions_for_tick(tick: int) -> Array:
	_current_tick = tick
	
	# Emit progress update
	if _metadata != null && tick % 30 == 0:  # Update every second
		replay_progress_updated.emit(tick, _metadata.total_ticks)
	
	# Check if replay finished
	if _metadata != null && tick >= _metadata.total_ticks && !_replay_finished:
		_replay_finished = true
		_is_playing = false
		replay_finished.emit()
		print("ReplayPlayer: Replay finished at tick ", tick)
	
	if !_is_playing:
		return []
	
	return _actions_by_tick.get(tick, [])


# Check if replay is currently playing
func is_playing() -> bool:
	return _is_playing


# Check if replay has finished
func has_finished() -> bool:
	return _replay_finished


# Get current tick
func get_current_tick() -> int:
	return _current_tick


# Get total ticks in replay
func get_total_ticks() -> int:
	return _metadata.total_ticks if _metadata != null else 0


#########################
###      Private      ###
#########################

func _count_total_actions() -> int:
	var count: int = 0
	for actions in _actions_by_tick.values():
		count += actions.size()
	return count

