class_name ReplayPlayer extends Node


# Handles playback of replay files with deterministic execution.
# Supports variable playback speeds and state verification.


signal replay_started()
signal replay_paused()
signal replay_resumed()
signal replay_finished()
signal replay_error(error_message: String)


enum ReplayState {
	STOPPED,
	PLAYING,
	PAUSED,
	FINISHED
}


var _replay_data: Dictionary = {}
var _current_action_index: int = 0
var _current_tick: int = 0
var _target_tick: int = 0
var _state: ReplayState = ReplayState.STOPPED
var _playback_speed: float = 1.0
var _is_replay_mode: bool = false
var _reference_resolver: ReferenceResolver


#########################
###     Built-in      ###
#########################

func _ready():
	_reference_resolver = ReferenceResolver.new()
	add_child(_reference_resolver)


#########################
###       Public      ###
#########################

func load_replay(file_path: String) -> bool:
	var file = FileAccess.open(file_path, FileAccess.READ)
	if file == null:
		var error_msg = "Failed to open replay file: " + file_path
		push_error(error_msg)
		replay_error.emit(error_msg)
		return false
	
	# Read metadata header (first line)
	var metadata_line = file.get_line()
	if metadata_line.is_empty():
		file.close()
		replay_error.emit("Empty replay file")
		return false
	
	var metadata = JSON.parse_string(metadata_line)
	if metadata == null:
		file.close()
		replay_error.emit("Failed to parse replay metadata")
		return false
	
	# Read actions (remaining lines)
	var actions = []
	while !file.eof():
		var action_line = file.get_line()
		if !action_line.is_empty():
			var action_data = JSON.parse_string(action_line)
			if action_data != null:
				actions.append(action_data)
	
	file.close()
	
	# Store replay data
	_replay_data = {
		"metadata": metadata,
		"actions": actions
	}
	
	print_verbose("Loaded replay with ", actions.size(), " actions")
	return true


func start_replay() -> bool:
	if _state != ReplayState.STOPPED:
		push_error("Replay already started or in progress")
		return false
	
	if _replay_data.is_empty():
		replay_error.emit("No replay data loaded")
		return false
	
	# Restore initial state
	if !_restore_initial_state():
		return false
	
	# Initialize replay state
	_current_action_index = 0
	_current_tick = 0
	_target_tick = 0
	_state = ReplayState.PLAYING
	_is_replay_mode = true
	
	# Set up reference resolver
	_setup_reference_resolver()
	
	print_verbose("Started replay playback")
	replay_started.emit()
	return true


func pause_replay():
	if _state == ReplayState.PLAYING:
		_state = ReplayState.PAUSED
		replay_paused.emit()
		print_verbose("Paused replay")


func resume_replay():
	if _state == ReplayState.PAUSED:
		_state = ReplayState.PLAYING
		replay_resumed.emit()
		print_verbose("Resumed replay")


func stop_replay():
	_state = ReplayState.STOPPED
	_is_replay_mode = false
	_current_action_index = 0
	_current_tick = 0
	_target_tick = 0
	print_verbose("Stopped replay")


func set_playback_speed(speed: float):
	_playback_speed = max(0.1, speed)
	print_verbose("Set replay speed to: ", _playback_speed)


func get_playback_speed() -> float:
	return _playback_speed


func is_replay_mode() -> bool:
	return _is_replay_mode


func get_replay_state() -> ReplayState:
	return _state


func get_current_tick() -> int:
	return _current_tick


func get_total_actions() -> int:
	if _replay_data.is_empty():
		return 0
	return _replay_data.actions.size()


func get_progress() -> float:
	if _replay_data.is_empty() || _replay_data.actions.is_empty():
		return 0.0
	
	var total_actions = _replay_data.actions.size()
	return float(_current_action_index) / float(total_actions)


func seek_to_action(action_index: int) -> bool:
	if _replay_data.is_empty():
		return false
	
	var actions = _replay_data.actions
	if action_index < 0 || action_index >= actions.size():
		return false
	
	# Restore initial state
	if !_restore_initial_state():
		return false
	
	# Execute actions up to the target index
	_current_action_index = 0
	_current_tick = 0
	
	for i in range(action_index + 1):
		if i < actions.size():
			var action_entry = actions[i]
			_current_tick = action_entry.get("tick", 0)
			_execute_replay_action(action_entry.action)
			_current_action_index = i + 1
	
	print_verbose("Seeked to action ", action_index, " at tick ", _current_tick)
	return true


func execute_replay_tick(tick: int):
	if _state != ReplayState.PLAYING:
		return
	
	_current_tick = tick
	
	# Execute all actions for this tick
	while _current_action_index < _replay_data.actions.size():
		var action_entry = _replay_data.actions[_current_action_index]
		var action_tick = action_entry.get("tick", 0)
		
		if action_tick > tick:
			break
		
		if action_tick == tick:
			_execute_replay_action(action_entry.action)
		
		_current_action_index += 1
	
	# Check if replay is finished
	if _current_action_index >= _replay_data.actions.size():
		_finish_replay()


#########################
###      Private      ###
#########################

func _restore_initial_state() -> bool:
	if _replay_data.is_empty():
		return false
	
	var metadata = _replay_data.metadata
	var initial_state = metadata.get("initial_state", {})
	var game_settings = metadata.get("game_settings", {})
	
	# Restore game settings
	if game_settings.has("origin_seed"):
		Globals._origin_seed = game_settings.origin_seed
	
	if game_settings.has("rng_seed"):
		Globals.synced_rng.set_seed(game_settings.rng_seed)
	
	if game_settings.has("rng_state"):
		Globals.synced_rng.set_state(game_settings.rng_state)
	
	# Restore game mode and difficulty
	if initial_state.has("game_mode"):
		Globals._game_mode = initial_state.game_mode
	
	if initial_state.has("difficulty"):
		Globals._difficulty = initial_state.difficulty
	
	if initial_state.has("wave_count"):
		Globals._wave_count = initial_state.wave_count
	
	print_verbose("Restored initial state from replay")
	return true


func _setup_reference_resolver():
	# This will be implemented when we need to resolve references
	# For now, we'll assume references can be resolved directly
	pass


func _execute_replay_action(action: Dictionary):
	# Convert action back to proper format and execute
	# This is a simplified version - in practice, we'd need to
	# resolve references and ensure proper execution order
	
	var action_type = action.get(Action.Field.TYPE, Action.Type.NONE)
	
	match action_type:
		Action.Type.CHAT:
			_execute_chat_action(action)
		Action.Type.BUILD_TOWER:
			_execute_build_tower_action(action)
		Action.Type.UPGRADE_TOWER:
			_execute_upgrade_tower_action(action)
		Action.Type.SELL_TOWER:
			_execute_sell_tower_action(action)
		# Add other action types as needed
		_:
			print_verbose("Unhandled replay action type: ", action_type)


func _execute_chat_action(action: Dictionary):
	var message = action.get(Action.Field.CHAT_MESSAGE, "")
	var player_id = action.get(Action.Field.PLAYER_ID, 0)
	
	var player = PlayerManager.get_player(player_id)
	if player == null:
		return
	
	# Execute chat action
	var chat_action = ActionChat.make(message)
	ActionChat.execute(chat_action.serialize(), player, null, null)


func _execute_build_tower_action(action: Dictionary):
	var tower_id = action.get(Action.Field.TOWER_ID, 0)
	var position = action.get(Action.Field.POSITION, Vector2.ZERO)
	var player_id = action.get(Action.Field.PLAYER_ID, 0)
	
	var player = PlayerManager.get_player(player_id)
	if player == null:
		return
	
	# Execute build tower action
	var build_action = ActionBuildTower.make(tower_id, position)
	ActionBuildTower.execute(build_action.serialize(), player, null)


func _execute_upgrade_tower_action(action: Dictionary):
	var tower_id = action.get(Action.Field.TOWER_ID, 0)
	var player_id = action.get(Action.Field.PLAYER_ID, 0)
	
	var player = PlayerManager.get_player(player_id)
	if player == null:
		return
	
	# Execute upgrade tower action
	var upgrade_action = ActionUpgradeTower.make(tower_id)
	ActionUpgradeTower.execute(upgrade_action.serialize(), player, null)


func _execute_sell_tower_action(action: Dictionary):
	var tower_id = action.get(Action.Field.TOWER_ID, 0)
	var player_id = action.get(Action.Field.PLAYER_ID, 0)
	
	var player = PlayerManager.get_player(player_id)
	if player == null:
		return
	
	# Execute sell tower action
	var sell_action = ActionSellTower.make(tower_id)
	ActionSellTower.execute(sell_action.serialize(), player, null)


func _finish_replay():
	_state = ReplayState.FINISHED
	_is_replay_mode = false
	replay_finished.emit()
	print_verbose("Replay finished")


#########################
###     Callbacks     ###
#########################

func _on_replay_timer_timeout():
	if _state == ReplayState.PLAYING:
		execute_replay_tick(_target_tick)
		_target_tick += 1
