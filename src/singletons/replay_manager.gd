class_name ReplayManager extends Node

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

var current_mode: ReplayMode = ReplayMode.NONE
var playback_state: PlaybackState = PlaybackState.STOPPED
var current_replay_file: String = ""

# Recording state
var _is_recording: bool = false
var _recorded_actions: Array = []
var _recording_start_tick: int = 0
var _last_checksum_tick: int = 0

# Playback state
var _is_playback: bool = false
var _playback_actions: Array = []
var _playback_tick: int = 0
var _playback_speed: float = 1.0
var _original_game_speed: int = 1

# State verification
var _state_verifier: StateVerifier
var _checksum_period: int = 90  # Every 90 ticks (3 seconds at 30 TPS) - more performance friendly
var _detailed_checksums_enabled: bool = false  # Disabled by default for better performance

# File paths
const REPLAY_DIR: String = "user://replays/"
const STATE_DIR: String = "user://replays/_state/"
const BACKUP_DIR: String = "user://replays/backups/"


#########################
###     Built-in      ###
#########################

func _ready():
	_state_verifier = StateVerifier.new()
	_state_verifier.set_checksum_frequency(_checksum_period)
	_state_verifier.set_detailed_checksums_enabled(_detailed_checksums_enabled)
	_create_directories()


func _physics_process(_delta: float):
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

	current_mode = ReplayMode.RECORDING
	_is_recording = true
	_recording_start_tick = _get_current_tick()

	# Generate unique replay ID
	current_replay_file = _generate_replay_id()
	_recorded_actions.clear()
	_last_checksum_tick = 0

	# Enable detailed checksums for recording to ensure accuracy
	_enable_recording_checksums()

	# Save metadata file
	_save_replay_metadata()

	# Backup current game state for restoration
	_backup_game_state()

	replay_mode_changed.emit(current_mode)
	return true


func stop_recording() -> bool:
	if current_mode != ReplayMode.RECORDING:
		return false

	current_mode = ReplayMode.NONE
	_is_recording = false

	# Restore performance-friendly checksum settings
	_restore_normal_checksums()

	# Update metadata with final information
	_update_replay_metadata()

	replay_mode_changed.emit(current_mode)
	return true


func start_playback(replay_id: String) -> bool:
	if current_mode != ReplayMode.NONE:
		return false

	var replay_data: Dictionary = _load_replay_file(replay_id)
	if replay_data.is_empty():
		return false

	# Store original game state for restoration
	_backup_game_state()

	# Load replay state
	_playback_actions = replay_data.get("actions", [])
	_playback_tick = 0
	_playback_speed = 1.0

	current_mode = ReplayMode.PLAYBACK
	_is_playback = true
	playback_state = PlaybackState.PLAYING

	# Load initial game state from replay
	_restore_initial_game_state(replay_data)

	replay_mode_changed.emit(current_mode)
	playback_state_changed.emit(playback_state)
	replay_loaded.emit(replay_id)

	return true


func stop_playback() -> bool:
	if current_mode != ReplayMode.PLAYBACK:
		return false

	current_mode = ReplayMode.NONE
	_is_playback = false
	playback_state = PlaybackState.STOPPED

	# Restore original game state
	_restore_original_game_state()

	replay_mode_changed.emit(current_mode)
	playback_state_changed.emit(playback_state)

	return true


func pause_playback() -> bool:
	if playback_state != PlaybackState.PLAYING:
		return false

	playback_state = PlaybackState.PAUSED
	playback_state_changed.emit(playback_state)
	return true


func resume_playback() -> bool:
	if playback_state != PlaybackState.PAUSED:
		return false

	playback_state = PlaybackState.PLAYING
	playback_state_changed.emit(playback_state)
	return true


func set_playback_speed(speed: float) -> bool:
	_playback_speed = max(0.1, min(5.0, speed))  # Clamp between 0.1x and 5.0x
	Globals.set_update_ticks_per_physics_tick(_original_game_speed * _playback_speed)
	return true


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
	# Replay is already being saved continuously as JSONL during recording
	# Just need to finalize metadata
	if current_mode == ReplayMode.RECORDING:
		_update_replay_metadata()
		return current_replay_file

	return ""


func verify_game_state() -> Dictionary:
	return _state_verifier.verify_current_state()


func set_checksum_frequency(ticks: int) -> void:
	_checksum_period = max(1, ticks)
	if _state_verifier:
		_state_verifier.set_checksum_frequency(_checksum_period)


func set_detailed_checksums_enabled(enabled: bool) -> void:
	_detailed_checksums_enabled = enabled
	if _state_verifier:
		_state_verifier.set_detailed_checksums_enabled(_detailed_checksums_enabled)


func get_checksum_frequency() -> int:
	return _checksum_period


func get_detailed_checksums_enabled() -> bool:
	return _detailed_checksums_enabled


func _enable_recording_checksums() -> void:
	# Enable detailed checksums with higher frequency for accurate recording
	_checksum_period = 30  # 1 second at 30 TPS
	_detailed_checksums_enabled = true

	if _state_verifier:
		_state_verifier.set_checksum_frequency(_checksum_period)
		_state_verifier.set_detailed_checksums_enabled(_detailed_checksums_enabled)


func _restore_normal_checksums() -> void:
	# Restore performance-friendly settings for normal gameplay
	_checksum_period = 90  # 3 seconds at 30 TPS
	_detailed_checksums_enabled = false

	if _state_verifier:
		_state_verifier.set_checksum_frequency(_checksum_period)
		_state_verifier.set_detailed_checksums_enabled(_detailed_checksums_enabled)


#########################
###      Private      ###
#########################

func _create_directories():
	var dirs: Array = [REPLAY_DIR, STATE_DIR, BACKUP_DIR]
	for dir_path in dirs:
		if !DirAccess.dir_exists_absolute(dir_path):
			DirAccess.make_dir_recursive_absolute(dir_path)


func _get_current_tick() -> int:
	# For now, use a simple counter based on elapsed time
	# In a real implementation, this would be synchronized with the game tick system
	return floori(Time.get_ticks_msec() / (1000.0 / 30.0))  # 30 ticks per second


func _update_recording():
	var current_tick: int = _get_current_tick()

	# Record periodic checksums if needed
	if _state_verifier.should_generate_checksum():
		_record_game_state_checksum(current_tick)


func _update_playback():
	if playback_state != PlaybackState.PLAYING:
		return

	var current_tick: int = _get_current_tick()

	# Execute actions for current tick
	while _playback_tick < _playback_actions.size():
		var action_data: Dictionary = _playback_actions[_playback_tick]
		var action_tick: int = action_data.get("tick", 0)

		if action_tick <= current_tick:
			_execute_replay_action(action_data)
			_playback_tick += 1
		else:
			break

	# Check if playback is finished
	if _playback_tick >= _playback_actions.size():
		_finish_playback()


func _record_action(action: Dictionary):
	if !_is_recording:
		return

	# Only record actions that are meaningful for replays
	var action_obj: Action = Action.new(action)
	if not action_obj.is_replayable():
		return

	var current_tick: int = _get_current_tick()
	var action_data: Dictionary = action.duplicate()
	action_data["tick"] = current_tick - _recording_start_tick

	# Append to JSONL file
	var replay_file_path: String = REPLAY_DIR + current_replay_file + ".jsonl"
	var file: FileAccess = FileAccess.open(replay_file_path, FileAccess.READ_WRITE)
	if file:
		file.seek_end()
		file.store_line(JSON.stringify(action_data))
		file.close()


func _record_game_state_checksum(tick: int):
	var checksum_data: Dictionary = _state_verifier.generate_checksum_tree()
	var checksum_file: String = STATE_DIR + current_replay_file + "-%d.json" % tick

	# Save checksum to file
	var file: FileAccess = FileAccess.open(checksum_file, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(checksum_data))
		file.close()


func _execute_replay_action(action_data: Dictionary):
	# Remove tick from action data before execution
	var action: Dictionary = action_data.duplicate()
	action.erase("tick")

	# Execute the action (same as normal execution but with recorded data)
	var action_type: Action.Type = action[Action.Field.TYPE]
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
		Action.Type.SELL_TOWER: _execute_sell_tower_action(action, player)
		Action.Type.SELECT_BUILDER: _execute_select_builder_action(action, player)
		Action.Type.TOGGLE_AUTOCAST: _execute_toggle_autocast_action(action, player)
		Action.Type.CONSUME_ITEM: _execute_consume_item_action(action, player)
		Action.Type.MOVE_ITEM: _execute_move_item_action(action, player)
		Action.Type.AUTOFILL: _execute_autofill_action(action, player)
		Action.Type.TRANSMUTE: _execute_transmute_action(action, player)
		Action.Type.RESEARCH_ELEMENT: _execute_research_element_action(action, player)
		Action.Type.ROLL_TOWERS: _execute_roll_towers_action(action, player)
		Action.Type.START_NEXT_WAVE: _execute_start_next_wave_action(action, player)
		Action.Type.AUTOCAST: _execute_autocast_action(action, player)
		Action.Type.FOCUS_TARGET: _execute_focus_target_action(action, player)
		Action.Type.CHANGE_BUFFGROUP: _execute_change_buffgroup_action(action, player)
		Action.Type.SELECT_WISDOM_UPGRADES: _execute_select_wisdom_upgrades_action(action, player)
		Action.Type.SORT_ITEM_STASH: _execute_sort_item_stash_action(action, player)


func _execute_chat_action(action: Dictionary, player: Player):
	var chat_commands: ChatCommands = get_node("/root/ChatCommands") if get_tree().root.has_node("ChatCommands") else null
	var hud: HUD = get_node("/root/HUD") if get_tree().root.has_node("HUD") else null

	if chat_commands and hud:
		ActionChat.execute(action, player, hud, chat_commands)


func _execute_build_tower_action(action: Dictionary, player: Player):
	var build_space: BuildSpace = get_node("/root/BuildSpace") if get_tree().root.has_node("BuildSpace") else null

	if build_space:
		ActionBuildTower.execute(action, player, build_space)


func _execute_upgrade_tower_action(action: Dictionary, player: Player):
	var select_unit: SelectUnit = get_node("/root/SelectUnit") if get_tree().root.has_node("SelectUnit") else null

	if select_unit:
		ActionUpgradeTower.execute(action, player, select_unit)


func _execute_sell_tower_action(action: Dictionary, player: Player):
	var build_space: BuildSpace = get_node("/root/BuildSpace") if get_tree().root.has_node("BuildSpace") else null

	if build_space:
		ActionSellTower.execute(action, player, build_space)


func _execute_select_builder_action(action: Dictionary, player: Player):
	ActionSelectBuilder.execute(action, player)


func _execute_toggle_autocast_action(action: Dictionary, player: Player):
	ActionToggleAutocast.execute(action, player)


func _execute_consume_item_action(action: Dictionary, player: Player):
	ActionConsumeItem.execute(action, player)


func _execute_move_item_action(action: Dictionary, player: Player):
	ActionMoveItem.execute(action, player)


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


func _execute_select_wisdom_upgrades_action(action: Dictionary, player: Player):
	ActionSelectWisdomUpgrades.execute(action, player)


func _execute_sort_item_stash_action(action: Dictionary, player: Player):
	ActionSortItemStash.execute(action, player)


func _finish_playback():
	playback_state = PlaybackState.FINISHED
	playback_state_changed.emit(playback_state)

	# Pause the game when replay finishes
	get_tree().paused = true


func _save_replay() -> String:
	var timestamp: String = Time.get_datetime_string_from_system().replace(":", "_").replace("-", "_")
	var filename: String = "replay_%s.replay" % timestamp
	var file_path: String = REPLAY_DIR + filename

	var replay_data: Dictionary = {
		"metadata": {
			"version": "1.0",
			"timestamp": Time.get_unix_time_from_system(),
			"game_seed": Globals.get_origin_seed(),
			"wave_count": Globals.get_wave_count(),
			"difficulty": Globals.get_difficulty(),
			"game_mode": Globals.get_game_mode(),
			"player_count": PlayerManager.get_player_list().size(),
		},
		"initial_state": _get_initial_game_state(),
		"actions": _recorded_actions,
		"checksums": _get_checksum_file_list(),
	}

	# Save to file
	var file: FileAccess = FileAccess.open(file_path, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(replay_data))
		file.close()

		current_replay_file = file_path
		replay_saved.emit(file_path)

		return file_path

	return ""


func _load_replay_file(replay_id: String) -> Dictionary:
	# Load metadata first
	var metadata_file: String = REPLAY_DIR + replay_id + ".json"
	var metadata_content: String = FileAccess.get_file_as_string(metadata_file)
	var metadata: Dictionary = JSON.parse_string(metadata_content)

	if !metadata:
		return {}

	# Load actions from JSONL file
	var actions: Array = []
	var jsonl_file: String = REPLAY_DIR + replay_id + ".jsonl"

	if FileAccess.file_exists(jsonl_file):
		var file: FileAccess = FileAccess.open(jsonl_file, FileAccess.READ)
		if file:
			while !file.eof_reached():
				var line: String = file.get_line()
				if !line.is_empty():
					var action: Dictionary = JSON.parse_string(line)
					if action:
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
		"globals": _serialize_globals(),
		"players": _serialize_players(),
		"towers": _serialize_towers(),
		"items": _serialize_items(),
		"wisdom_upgrades": _serialize_wisdom_upgrades(),
	}


func _restore_initial_game_state(replay_data: Dictionary):
	var initial_state: Dictionary = replay_data.get("initial_state", {})

	# Restore globals
	_restore_globals(initial_state.get("globals", {}))

	# Restore players
	_restore_players(initial_state.get("players", []))

	# Restore towers
	_restore_towers(initial_state.get("towers", []))

	# Restore items
	_restore_items(initial_state.get("items", []))

	# Restore wisdom upgrades
	_restore_wisdom_upgrades(initial_state.get("wisdom_upgrades", {}))


func _backup_game_state():
	# This would need to be implemented to save current state before replay
	# For now, just store basic globals
	pass


func _restore_original_game_state():
	# This would need to be implemented to restore state after replay
	# For now, just reset to normal mode
	current_mode = ReplayMode.NONE
	playback_state = PlaybackState.STOPPED


func _serialize_globals() -> Dictionary:
	return {
		"origin_seed": Globals.get_origin_seed(),
		"wave_count": Globals.get_wave_count(),
		"difficulty": Globals.get_difficulty(),
		"game_mode": Globals.get_game_mode(),
		"team_mode": Globals.get_team_mode(),
	}


func _serialize_players() -> Array:
	var players: Array = []
	var player_list: Array = PlayerManager.get_player_list()

	for player in player_list:
		players.append({
			"id": player.get_id(),
			"name": player.get_player_name(),
			"experience": player.get_experience(),
			"gold": player.get_gold(),
		})

	return players


func _serialize_towers() -> Array:
	var towers: Array = []
	var tower_list: Array = Utils.get_tower_list()

	for tower in tower_list:
		towers.append({
			"uid": tower.get_uid(),
			"id": tower.get_id(),
			"position": [tower.position.x, tower.position.y],
			"player_id": tower.get_player().get_id(),
			"experience": tower.get_experience(),
			"damage_dealt": tower.get_damage_dealt(),
		})

	return towers


func _serialize_items() -> Array:
	# Implementation needed for item serialization
	return []


func _serialize_wisdom_upgrades() -> Dictionary:
	return Settings.get_wisdom_upgrades()


func _restore_globals(globals_data: Dictionary):
	Globals._origin_seed = globals_data.get("origin_seed", 0)
	Globals._wave_count = globals_data.get("wave_count", 0)
	Globals._difficulty = globals_data.get("difficulty", 0)
	Globals._game_mode = globals_data.get("game_mode", 0)
	Globals._team_mode = globals_data.get("team_mode", 0)


func _restore_players(players_data: Array):
	# Implementation needed for player restoration
	# For now, just ensure players exist
	pass


func _restore_towers(towers_data: Array):
	# Implementation needed for tower restoration
	# For now, just clear existing towers
	var tower_list: Array = Utils.get_tower_list()
	for tower in tower_list:
		if tower.get_player() == PlayerManager.get_local_player():
			tower.queue_free()


func _restore_items(items_data: Array):
	# Implementation needed for item restoration
	# For now, just clear player items
	var local_player: Player = PlayerManager.get_local_player()
	if local_player:
		var item_stash: ItemContainer = local_player.get_item_stash()
		var horadric_stash: ItemContainer = local_player.get_horadric_stash()

		# Clear existing items
		var items_to_remove: Array = []
		items_to_remove.append_array(item_stash.get_item_list())
		items_to_remove.append_array(horadric_stash.get_item_list())

		for item in items_to_remove:
			item_stash.remove_item(item)
			horadric_stash.remove_item(item)


func _restore_wisdom_upgrades(upgrades_data: Dictionary):
	Settings.set_wisdom_upgrades(upgrades_data)


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
		"player_count": PlayerManager.get_player_list().size(),
		"recording_start_tick": _recording_start_tick,
		"checksum_period": _checksum_period,
		"detailed_checksums": _detailed_checksums_enabled,
	}

	var metadata_file: String = REPLAY_DIR + current_replay_file + ".json"
	var file: FileAccess = FileAccess.open(metadata_file, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(metadata, "\t"))
		file.close()


func _update_replay_metadata() -> void:
	var metadata_file: String = REPLAY_DIR + current_replay_file + ".json"
	var file: FileAccess = FileAccess.open(metadata_file, FileAccess.READ)
	if !file:
		return

	var content: String = file.get_as_text()
	file.close()

	var metadata: Dictionary = JSON.parse_string(content)
	if metadata:
		metadata["recording_end_tick"] = _get_current_tick()
		metadata["duration_ticks"] = metadata["recording_end_tick"] - metadata["recording_start_tick"]

		file = FileAccess.open(metadata_file, FileAccess.WRITE)
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
