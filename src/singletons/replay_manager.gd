extends Node

# Main singleton for managing replay functionality
# Handles recording, playback, and state verification

enum ReplayMode {
	NONE,        # Normal gameplay
	RECORDING,   # Recording actions for replay
	PLAYBACK,    # Playing back a replay
}

enum PlaybackState {
	STOPPED,
	PLAYING,
	PAUSED,
	FINISHED,
}

signal replay_mode_changed(mode: ReplayMode)
signal playback_state_changed(state: PlaybackState)
signal replay_loaded(replay_file_path: String)
signal replay_saved(replay_file_path: String)
signal state_verification_failed(error_details: Dictionary)
signal continue_pressed()

var current_mode: ReplayMode = ReplayMode.NONE
var playback_state: PlaybackState = PlaybackState.STOPPED
var current_replay_file: String = ""

var _game_client: GameClient

# Recording state
var _recorded_actions: Array = []  # Store actions in memory for binary serialization
var _recording_start_tick: int = 0
var _last_checksum_tick: int = 0
var _initial_game_state: Dictionary = {}

# Playback state
var _playback_actions: Array = []
var _playback_tick: int = 0

# State verification
var _state_verifier: StateVerifier
var _checksum_period: int = 300
var _detailed_checksums_enabled: bool = true

# File paths
const REPLAY_DIR: String = "user://replays/"
const STATE_DIR: String = "user://replays/_state/"
const BACKUP_DIR: String = "user://replays/backups/"


#########################
###     Built-in      ###
#########################

func _ready():
	_state_verifier = StateVerifier.new()
	add_child(_state_verifier)
	_state_verifier.set_detailed_checksums_enabled(_detailed_checksums_enabled)
	_create_directories()

func tick():
	match current_mode:
		ReplayMode.RECORDING:
			_update_recording()
		ReplayMode.PLAYBACK:
			_update_playback()


#########################
###       Public      ###
#########################

func start_recording() -> bool:
	if current_mode != ReplayMode.NONE:
		return false
	
	_restore_original_state()

	current_mode = ReplayMode.RECORDING
	_initial_game_state = _get_initial_game_state()

	# Generate unique replay ID
	current_replay_file = _generate_replay_id()

	replay_mode_changed.emit(current_mode)
	return true


# func stop_recording() -> bool:
# 	if current_mode != ReplayMode.RECORDING:
# 		return false

# 	current_mode = ReplayMode.NONE

# 	# Save replay
# 	var binary_file_path: String = _save_replay()

# 	replay_mode_changed.emit(current_mode)
# 	return true


func start_playback(replay_id: String) -> bool:
	if current_mode != ReplayMode.NONE:
		return false
	
	_restore_original_state()
	
	current_replay_file = replay_id
	var replay_data: Dictionary = _load_replay_file(replay_id)
	if replay_data.is_empty():
		return false
	
	# Store original player data for restoration
	if _should_backup_data(replay_data):
		_backup_data()

	# Load replay state
	_playback_actions = replay_data.get("actions", [])

	current_mode = ReplayMode.PLAYBACK
	playback_state = PlaybackState.PLAYING

	# Load initial game state from replay
	_restore_initial_game_state(replay_data)

	replay_mode_changed.emit(current_mode)
	playback_state_changed.emit(playback_state)
	replay_loaded.emit(replay_id)

	return true


# func stop_playback() -> bool:
# 	if current_mode != ReplayMode.PLAYBACK:
# 		return false

# 	current_mode = ReplayMode.NONE
# 	playback_state = PlaybackState.STOPPED

# 	# Restore original game state
# 	_restore_original_state()

# 	replay_mode_changed.emit(current_mode)
# 	playback_state_changed.emit(playback_state)

# 	return true


# func pause_playback() -> bool:
# 	if playback_state != PlaybackState.PLAYING:
# 		return false

# 	playback_state = PlaybackState.PAUSED
# 	playback_state_changed.emit(playback_state)
# 	return true


# func resume_playback() -> bool:
# 	if playback_state != PlaybackState.PAUSED:
# 		return false

# 	playback_state = PlaybackState.PLAYING
# 	playback_state_changed.emit(playback_state)
# 	return true


func is_recording() -> bool:
	return current_mode == ReplayMode.RECORDING


func is_playing() -> bool:
	return current_mode == ReplayMode.PLAYBACK && playback_state == PlaybackState.PLAYING


func get_replay_list() -> Array:
	var replays: Array = []
	var dir: DirAccess = DirAccess.open(REPLAY_DIR)

	if dir:
		dir.list_dir_begin()
		var file_name: String = dir.get_next()

		while file_name != "":
			if file_name.ends_with(".json") && file_name.begins_with("replay_"):
				# Extract replay ID from metadata file name
				var replay_id: String = file_name.get_basename()
				var replay_info: Dictionary = _get_replay_info(replay_id)
				if !replay_info.is_empty():
					replays.append(replay_info)

			file_name = dir.get_next()

		dir.list_dir_end()

	replays.sort_custom(func(a, b): return a["timestamp"] > b["timestamp"])
	return replays


func save_replay_from_current_game() -> String:
	if current_mode == ReplayMode.RECORDING:
		# Save the current recording and return the replay ID
		var binary_file_path: String = _save_replay()
		return binary_file_path

	return ""

func get_checksum_filename(tick: int) -> String:
	return STATE_DIR + current_replay_file + "-%d.json" % tick

func verify_replay_state_at_tick(tick: int) -> Dictionary:
	"""Verify the current game state against the recorded checksum at a specific tick"""
	var checksum_file: String = get_checksum_filename(tick)
	var result: Dictionary = _state_verifier.verify_against_recorded_state(checksum_file)

	# Add tick information to result
	result["tick"] = tick

	# Emit signal for UI feedback (but we removed this signal, so we'll handle it differently)
	if not result.get("valid", true):
		# Could emit a different signal or handle this in the calling code
		var num_diffs: int = result["differences"].size()
		Messages.add_error(PlayerManager.get_local_player(), "Invalid replay state! Num differences: %d" % num_diffs)
	else:
		Messages.add_normal(PlayerManager.get_local_player(), "Replay state is correct!")

	return result


func is_tick_checksum_available(tick: int) -> bool:
	"""Check if a checksum is available for the given tick"""
	var checksum_file: String = get_checksum_filename(tick)
	return FileAccess.file_exists(checksum_file)

#########################
###      Private      ###
#########################

func _get_game_client() -> GameClient:
	if is_instance_valid(_game_client):
		return _game_client
	var game_client: GameClient = get_tree().root.find_child("GameClient", true, false)
	_game_client = game_client
	return _game_client


func _get_select_unit() -> SelectUnit:
	return _get_game_client()._select_unit


func _get_build_space() -> BuildSpace:
	return _get_game_client()._build_space


func _get_chat_commands() -> ChatCommands:
	return _get_game_client()._chat_commands


func _get_hud() -> HUD:
	return _get_game_client()._hud

func _create_directories():
	var dirs: Array = [REPLAY_DIR, STATE_DIR, BACKUP_DIR]
	for dir_path in dirs:
		if !DirAccess.dir_exists_absolute(dir_path):
			DirAccess.make_dir_recursive_absolute(dir_path)


func _get_current_tick() -> int:
	var game_client: GameClient = _get_game_client()
	if is_instance_valid(game_client):
		return _get_game_client()._current_tick
	return 0

func _should_generate_checksum() -> bool:
	var current_tick: int = _get_current_tick()
	return current_tick - _last_checksum_tick >= _checksum_period

func _update_recording():
	var current_tick: int = _get_current_tick()

	# Record periodic checksums if needed
	if _should_generate_checksum():
		_record_game_state_checksum(current_tick)


func _update_playback():
	if playback_state != PlaybackState.PLAYING:
		return

	var current_tick: int = _get_current_tick() - _recording_start_tick

	# Execute actions for current tick
	while _playback_tick < _playback_actions.size():
		var action_data: Dictionary = _playback_actions[_playback_tick]
		var action_tick: int = action_data.get("tick", 0)

		if action_tick <= current_tick:
			_execute_replay_action(action_data)
			_playback_tick += 1
		else:
			break

	# Verify state against recorded checksums periodically
	var should_generate: bool = _should_generate_checksum()
	var is_checksum_available: bool = is_tick_checksum_available(current_tick)
	if should_generate:
		if is_checksum_available:
			var verification_result: Dictionary = verify_replay_state_at_tick(current_tick)
			
			#if not verification_result.get("valid", true):
				## Pause playback if state verification fails
				#playback_state = PlaybackState.PAUSED
				#playback_state_changed.emit(playback_state)

	# Check if playback is finished
	if _playback_tick >= _playback_actions.size():
		_finish_playback()


func _record_action(action: Dictionary):
	if !is_recording():
		return

	# Only record actions that are meaningful for replays
	var action_obj: Action = Action.new(action)
	if not action_obj.is_replayable():
		return

	var current_tick: int = _get_current_tick()
	var action_data: Dictionary = action.duplicate()
	action_data["tick"] = current_tick - _recording_start_tick

	# Store action in memory for binary serialization
	_recorded_actions.append(action_data)


func _record_game_state_checksum(tick: int):
	var checksum_data: Dictionary = _state_verifier.generate_checksum_tree()
	var checksum_file: String = get_checksum_filename(tick)
	
	# Update last checksum tick
	_last_checksum_tick = _get_current_tick()
	
	# Save checksum to file
	var file: FileAccess = FileAccess.open(checksum_file, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(checksum_data))
		file.close()


func _save_replay() -> String:
	if _recorded_actions.is_empty():
		return ""

	# Generate filename if not already set
	if current_replay_file.is_empty():
		current_replay_file = _generate_replay_id()

	var binary_file_path: String = REPLAY_DIR + current_replay_file + ".bin"
	var file: FileAccess = FileAccess.open(binary_file_path, FileAccess.WRITE)

	if file:
		# Write the number of actions first (as a 32-bit integer)
		file.store_32(_recorded_actions.size())

		# Write each action as a Godot variant (preserves types)
		for action_data in _recorded_actions:
			file.store_var(action_data)

		file.close()

		# Save metadata file as well
		_save_replay_metadata()

		replay_saved.emit(current_replay_file)
		return current_replay_file

	return ""


func _execute_replay_action(action_data: Dictionary):
	# Remove tick from action data before execution
	var action_copy: Dictionary = action_data.duplicate()
	action_copy.erase("tick")
	
	var action := {}
	for k in action_copy.keys():
		action[int(k)] = action_copy[k]
	
	# Execute the action (same as normal execution but with recorded data)
	var action_type: Action.Type = action[Action.Field.TYPE]
	if not Action.is_replayable_type(action_type):
		return
		
	var player_id: int = action[Action.Field.PLAYER_ID]
	var player: Player = PlayerManager.get_player(player_id)

	if player == null:
		return

	# Execute based on action type using the same logic as GameClient
	match action_type:
		Action.Type.IDLE: return
		Action.Type.CHAT: _execute_chat_action(action, player)
		Action.Type.BUILD_TOWER: _execute_build_tower_action(action, player)
		Action.Type.UPGRADE_TOWER: _execute_upgrade_tower_action(action, player)
		Action.Type.TRANSFORM_TOWER: _execute_transform_tower_action(action, player)
		Action.Type.SELL_TOWER: _execute_sell_tower_action(action, player)
		Action.Type.SELECT_BUILDER: _execute_select_builder_action(action, player)
		Action.Type.SELECT_WISDOM_UPGRADES: _execute_select_wisdom_upgrades_action(action, player)
		Action.Type.TOGGLE_AUTOCAST: _execute_toggle_autocast_action(action, player)
		Action.Type.CONSUME_ITEM: _execute_consume_item_action(action, player)
		Action.Type.DROP_ITEM: _execute_drop_item_action(action, player)
		Action.Type.MOVE_ITEM: _execute_move_item_action(action, player)
		Action.Type.SWAP_ITEMS: _execute_swap_items_action(action, player)
		Action.Type.AUTOFILL: _execute_autofill_action(action, player)
		Action.Type.TRANSMUTE: _execute_transmute_action(action, player)
		Action.Type.RESEARCH_ELEMENT: _execute_research_element_action(action, player)
		Action.Type.ROLL_TOWERS: _execute_roll_towers_action(action, player)
		Action.Type.START_NEXT_WAVE: _execute_start_next_wave_action(action, player)
		Action.Type.AUTOCAST: _execute_autocast_action(action, player)
		Action.Type.FOCUS_TARGET: _execute_focus_target_action(action, player)
		Action.Type.CHANGE_BUFFGROUP: _execute_change_buffgroup_action(action, player)
		Action.Type.SELECT_UNIT: _execute_select_unit_action(action, player)
		Action.Type.SORT_ITEM_STASH: _execute_sort_item_stash_action(action, player)


func _execute_chat_action(action: Dictionary, player: Player):
	var chat_commands: ChatCommands = _get_chat_commands()
	var hud: HUD = _get_hud()
	
	# code below allows to recreate selected unit for chat commands
	# such as autooil
	# just as the chat action is executed
	# without fully tracking selected units otherwise
	# nor requiring selected unit consistency for replays
	var selected_unit_uid: int = action[Action.Field.UID]
	var action_select_unit: Action = ActionSelectUnit.make(selected_unit_uid)
	ActionSelectUnit.execute(action_select_unit.serialize(), player)
	
	if chat_commands and hud:
		ActionChat.execute(action, player, hud, chat_commands)


func _execute_build_tower_action(action: Dictionary, player: Player):
	var build_space: BuildSpace = _get_build_space()

	if build_space:
		ActionBuildTower.execute(action, player, build_space)


func _execute_upgrade_tower_action(action: Dictionary, player: Player):
	var select_unit: SelectUnit = _get_select_unit()

	if select_unit:
		ActionUpgradeTower.execute(action, player, select_unit)


func _execute_transform_tower_action(action: Dictionary, player: Player):
	ActionTransformTower.execute(action, player)


func _execute_sell_tower_action(action: Dictionary, player: Player):
	var build_space: BuildSpace = _get_build_space()

	if build_space:
		ActionSellTower.execute(action, player, build_space)


func _execute_select_builder_action(action: Dictionary, player: Player):
	ActionSelectBuilder.execute(action, player)


func _execute_toggle_autocast_action(action: Dictionary, player: Player):
	ActionToggleAutocast.execute(action, player)


func _execute_consume_item_action(action: Dictionary, player: Player):
	ActionConsumeItem.execute(action, player)


func _execute_drop_item_action(action: Dictionary, player: Player):
	ActionDropItem.execute(action, player)


func _execute_move_item_action(action: Dictionary, player: Player):
	ActionMoveItem.execute(action, player)


func _execute_swap_items_action(action: Dictionary, player: Player):
	ActionSwapItems.execute(action, player)


func _execute_autofill_action(action: Dictionary, player: Player):
	ActionAutofill.execute(action, player)


func _execute_transmute_action(action: Dictionary, player: Player):
	ActionTransmute.execute(action, player)


func _execute_research_element_action(action: Dictionary, player: Player):
	ActionResearchElement.execute(action, player)


func _execute_roll_towers_action(action: Dictionary, player: Player):
	ActionRollTowers.execute(action, player)


func _execute_start_next_wave_action(action: Dictionary, player: Player):
	ActionStartNextWave.execute(action, player)


func _execute_autocast_action(action: Dictionary, player: Player):
	ActionAutocast.execute(action, player)


func _execute_focus_target_action(action: Dictionary, player: Player):
	ActionFocusTarget.execute(action, player)


func _execute_change_buffgroup_action(action: Dictionary, player: Player):
	ActionChangeBuffgroup.execute(action, player)


func _execute_select_unit_action(action: Dictionary, player: Player):
	ActionSelectUnit.execute(action, player)


func _execute_select_wisdom_upgrades_action(action: Dictionary, player: Player):
	ActionSelectWisdomUpgrades.execute(action, player)


func _execute_sort_item_stash_action(action: Dictionary, player: Player):
	ActionSortItemStash.execute(action, player)


func _finish_playback():
	playback_state = PlaybackState.FINISHED
	playback_state_changed.emit(playback_state)

	# Pause the game when replay finishes - use continue_pressed signal to pause the game in singleplayer
	continue_pressed.emit()


func _load_replay_file(replay_id: String) -> Dictionary:
	# Load metadata first
	var metadata_file: String = REPLAY_DIR + replay_id + ".json"
	var metadata_content: String = FileAccess.get_file_as_string(metadata_file)
	var metadata: Dictionary = JSON.parse_string(metadata_content)

	if !metadata:
		return {}

	# Load actions from binary file
	var actions: Array = []
	var binary_file: String = REPLAY_DIR + replay_id + ".bin"

	if FileAccess.file_exists(binary_file):
		var file: FileAccess = FileAccess.open(binary_file, FileAccess.READ)
		if file:
			# Read the number of actions first
			var action_count: int = file.get_32()

			# Read each action as a Godot variant (preserves types)
			for i in range(action_count):
				var action = file.get_var()
				if action != null:
					actions.append(action)

			file.close()

	metadata["actions"] = actions
	metadata["state_files"] = _get_state_file_list_for_replay(replay_id)

	return metadata


func _get_state_file_list_for_replay(replay_id: String) -> Array:
	var state_files: Array = []
	var metadata_file: String = REPLAY_DIR + replay_id + ".json"
	var metadata_content: String = FileAccess.get_file_as_string(metadata_file)
	var metadata: Dictionary = JSON.parse_string(metadata_content)

	if metadata:
		var start_tick: int = metadata.get("recording_start_tick", 0)
		var checksum_period: int = metadata.get("checksum_period", 30)

		for tick in range(start_tick, metadata.get("recording_end_tick", start_tick) + 1, checksum_period):
			var state_file: String = replay_id + "-%d.json" % tick
			if FileAccess.file_exists(STATE_DIR + state_file):
				state_files.append({
					"tick": tick,
					"file": state_file,
				})

	return state_files


func _get_replay_info(replay_id: String) -> Dictionary:
	var replay_data: Dictionary = _load_replay_file(replay_id)
	if replay_data.is_empty():
		return {}

	return {
		"replay_id": replay_id,
		"timestamp": replay_data.get("timestamp", 0),
		"wave_count": replay_data.get("wave_count", 0),
		"difficulty": replay_data.get("difficulty", 0),
		"game_mode": replay_data.get("game_mode", 0),
		"duration": _calculate_replay_duration(replay_data),
	}


func _calculate_replay_duration(replay_data: Dictionary) -> int:
	var duration_ticks: int = replay_data.get("duration_ticks", 0)
	if duration_ticks > 0:
		return duration_ticks / 30  # Convert ticks to seconds

	# Fallback calculation if duration not available
	var actions: Array = replay_data.get("actions", [])
	if actions.is_empty():
		return 0

	var first_tick: int = actions[0].get("tick", 0)
	var last_tick: int = actions[-1].get("tick", 0)

	return (last_tick - first_tick) / 30  # Convert ticks to seconds


func _get_initial_game_state() -> Dictionary:
	# Capture current game state for restoration
	return {
		"static_var_states": _serialize_static_var_states(),
		"globals": _serialize_globals(),
		"wisdom_upgrades": _serialize_wisdom_upgrades(),
		"exp_password": Settings.get_setting(Settings.EXP_PASSWORD),
	}


func _restore_initial_game_state(replay_data: Dictionary):
	var initial_state: Dictionary = replay_data.get("initial_state", {})

	_restore_exp_password(initial_state.get("exp_password", ""))
	_restore_static_var_states(initial_state.get("static_var_states", {}))
	_restore_globals(initial_state.get("globals", {}))
	_restore_wisdom_upgrades(initial_state.get("wisdom_upgrades", {}))


func _should_backup_data(replay_data: Dictionary):
	var initial_state: Dictionary = replay_data.get("initial_state", {})
	var replay_exp_password: String = initial_state.get("exp_password", "")
	
	var exp_password: String = Settings.get_setting(Settings.EXP_PASSWORD)
	
	if replay_exp_password != exp_password:
		return true
	return false
	

func _backup_data():
	# This would need to be implemented to save current state before replay
	# Write exp password to a backup file for that replay
	
	var exp_password: String = Settings.get_setting(Settings.EXP_PASSWORD)
	var amount_exp: int = ExperiencePassword.decode(exp_password)
	
	var backup_data: Dictionary = {
		"exp_password": exp_password,
		"amount_exp": amount_exp,
	}
	
	var filename: String = "exp_%d" % amount_exp
	
	var backup_file: String = BACKUP_DIR + filename + ".json"
	var file: FileAccess = FileAccess.open(backup_file, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(backup_data))
		file.close()


func _restore_original_state():
	# This would need to be implemented to restore state after replay
	# For now, just reset to normal mode
	current_mode = ReplayMode.NONE
	playback_state = PlaybackState.STOPPED
	current_replay_file = ""

	_recorded_actions.clear()
	_recording_start_tick = 0
	_last_checksum_tick = 0

	_playback_actions.clear()
	_playback_tick = 0
	_checksum_period = 300
	_detailed_checksums_enabled = true
	_state_verifier.set_detailed_checksums_enabled(_detailed_checksums_enabled)
	
	_game_client = null
	_state_verifier._game_client = null


func _serialize_static_var_states() -> Dictionary:
	return {
		"ItemContainerUidMax": ItemContainer._uid_max,
		"ItemUidMax": Item._uid_max,
		"AutocastUidMax": Autocast._uid_max,
		"UnitUidMax": Unit._uid_max,
	}


func _restore_static_var_states(static_var_states: Dictionary):
	ItemContainer._uid_max = static_var_states.get("ItemContainerUidMax", 1)
	Item._uid_max = static_var_states.get("ItemUidMax", 1)
	Autocast._uid_max = static_var_states.get("AutocastUidMax", 1)
	Unit._uid_max = static_var_states.get("UnitUidMax", 1)


func _serialize_globals() -> Dictionary:
	return {
		"origin_seed": Globals.get_origin_seed(),
		"wave_count": Globals.get_wave_count(),
		"difficulty": Globals.get_difficulty(),
		"game_mode": Globals.get_game_mode(),
		"team_mode": Globals.get_team_mode(),
	}


func _serialize_wisdom_upgrades() -> Dictionary:
	return Settings.get_wisdom_upgrades()


func _restore_exp_password(exp_password: String):
	Settings.set_setting(Settings.EXP_PASSWORD, exp_password)
	Settings.flush()

func _restore_globals(globals_data: Dictionary):
	Globals._origin_seed = globals_data.get("origin_seed", 0)
	Globals._wave_count = globals_data.get("wave_count", 0)
	Globals._difficulty = globals_data.get("difficulty", 0)
	Globals._game_mode = globals_data.get("game_mode", 0)
	Globals._team_mode = globals_data.get("team_mode", 0)


func _restore_wisdom_upgrades(upgrades_data: Dictionary):
	Settings.set_setting(Settings.WISDOM_UPGRADES_CACHED, upgrades_data)


func _generate_replay_id() -> String:
	# Generate unique ID based on timestamp and random component
	var timestamp: String = str(Time.get_unix_time_from_system()).replace(".", "_")
	var random_component: String = str(randi() % 10000).pad_zeros(4)
	return "replay_%s_%s" % [timestamp, random_component]


func _save_replay_metadata() -> void:
	var metadata: Dictionary = {
		"version": "1.0",
		"replay_id": current_replay_file,
		"timestamp": Time.get_unix_time_from_system(),
		"game_seed": Globals.get_origin_seed(),
		"wave_count": Globals.get_wave_count(),
		"difficulty": Globals.get_difficulty(),
		"game_mode": Globals.get_game_mode(),
		"team_mode": Globals.get_team_mode(),
		"player_count": PlayerManager.get_player_list().size(),
		"recording_start_tick": _recording_start_tick,
		"checksum_period": _checksum_period,
		"detailed_checksums": _detailed_checksums_enabled,
		"recording_end_tick": _get_current_tick(),
		"duration_ticks": _get_current_tick() - _recording_start_tick,
		"initial_state": _initial_game_state,
	}

	var metadata_file: String = REPLAY_DIR + current_replay_file + ".json"
	var file: FileAccess = FileAccess.open(metadata_file, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(metadata, "\t"))
		file.close()


func _get_state_file_list() -> Array:
	var state_files: Array = []
	var current_tick: int = _get_current_tick()

	for tick in range(_recording_start_tick, current_tick + 1, _checksum_period):
		var state_file: String = current_replay_file + "-%d.json" % tick
		if FileAccess.file_exists(STATE_DIR + state_file):
			state_files.append({
				"tick": tick,
				"file": state_file,
			})

	return state_files
