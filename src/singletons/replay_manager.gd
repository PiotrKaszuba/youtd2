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
var _playback_duration_ticks: int = 0

# Branch metadata. These fields are additive and old replay files remain valid.
var _parent_replay_id: String = ""
var _branch_tick: int = -1
var _settings_before_playback: Dictionary = {}

# State verification
var _state_verifier: StateVerifier
var _checksum_period: int = 300
var _detailed_checksums_enabled: bool = true
var _verification_start_tick: int = 0

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

	current_mode = ReplayMode.RECORDING
	playback_state = PlaybackState.STOPPED
	_recorded_actions.clear()
	_recording_start_tick = _get_current_tick()
	_last_checksum_tick = _recording_start_tick
	_verification_start_tick = _recording_start_tick
	_initial_game_state = _get_initial_game_state()
	_parent_replay_id = ""
	_branch_tick = -1

	# Generate unique replay ID
	current_replay_file = _generate_replay_id()

	replay_mode_changed.emit(current_mode)
	return true


func stop_recording() -> String:
	if current_mode != ReplayMode.RECORDING:
		return ""

	var replay_id: String = _save_replay()
	if replay_id.is_empty():
		return ""

	current_mode = ReplayMode.NONE
	replay_mode_changed.emit(current_mode)
	return replay_id


func start_playback(replay_id: String) -> bool:
	if current_mode != ReplayMode.NONE:
		return false
	
	_clear_session_state()
	
	current_replay_file = replay_id
	var replay_data: Dictionary = _load_replay_file(replay_id)
	if replay_data.is_empty():
		return false

	_settings_before_playback = {
		"exp_password": Settings.get_setting(Settings.EXP_PASSWORD),
		"wisdom_upgrades": Settings.get_wisdom_upgrades().duplicate(true),
	}
	
	# Store original player data for restoration
	if _should_backup_data(replay_data):
		_backup_data()

	# Load replay state
	_playback_actions = replay_data.get("actions", [])
	_playback_duration_ticks = replay_data.get("duration_ticks", 0)
	if _playback_duration_ticks <= 0 && !_playback_actions.is_empty():
		_playback_duration_ticks = _playback_actions.back().get("tick", 0) + 1
	_initial_game_state = replay_data.get("initial_state", {}).duplicate(true)
	_parent_replay_id = replay_data.get("parent_replay_id", "")
	_branch_tick = replay_data.get("branch_tick", -1)
	_checksum_period = replay_data.get("checksum_period", 300)
	_detailed_checksums_enabled = replay_data.get("detailed_checksums", true)
	_state_verifier.set_detailed_checksums_enabled(_detailed_checksums_enabled)
	_verification_start_tick = replay_data.get(
		"verification_start_tick",
		replay_data.get("recording_start_tick", 0),
	)
	_last_checksum_tick = _verification_start_tick

	current_mode = ReplayMode.PLAYBACK
	playback_state = PlaybackState.PLAYING

	# Load initial game state from replay
	_restore_initial_game_state(replay_data)

	replay_mode_changed.emit(current_mode)
	playback_state_changed.emit(playback_state)
	replay_loaded.emit(replay_id)

	return true


# Called after GameScene resets UidMaxTracker and before it creates players or
# other initial game objects. Playback state was loaded on the title screen.
func prepare_game_scene():
	if current_mode == ReplayMode.PLAYBACK:
		_restore_static_var_states(_initial_game_state.get("static_var_states", {}))
	elif current_mode == ReplayMode.NONE && Globals.get_player_mode() == PlayerMode.enm.SINGLEPLAYER:
		start_recording()


func branch_recording_from_playback() -> bool:
	var can_branch: bool = current_mode == ReplayMode.PLAYBACK && playback_state in [
		PlaybackState.PLAYING,
		PlaybackState.PAUSED,
		PlaybackState.FINISHED,
	]
	if !can_branch:
		return false

	var source_replay_id: String = current_replay_file
	_recorded_actions.clear()
	for index in range(_playback_tick):
		_recorded_actions.append(_playback_actions[index].duplicate(true))
	_recording_start_tick = 0
	_branch_tick = _get_current_tick()
	_verification_start_tick = _branch_tick
	_last_checksum_tick = _branch_tick
	_parent_replay_id = source_replay_id
	current_replay_file = _generate_replay_id()

	_playback_actions.clear()
	_playback_tick = 0
	_playback_duration_ticks = 0
	current_mode = ReplayMode.RECORDING
	playback_state = PlaybackState.STOPPED

	playback_state_changed.emit(playback_state)
	replay_mode_changed.emit(current_mode)
	return true


func pause_playback() -> bool:
	if current_mode != ReplayMode.PLAYBACK || playback_state != PlaybackState.PLAYING:
		return false

	playback_state = PlaybackState.PAUSED
	playback_state_changed.emit(playback_state)
	return true


func resume_playback() -> bool:
	if current_mode != ReplayMode.PLAYBACK || playback_state != PlaybackState.PAUSED:
		return false

	playback_state = PlaybackState.PLAYING
	playback_state_changed.emit(playback_state)
	return true


func finish_zero_duration_playback():
	if current_mode == ReplayMode.PLAYBACK && playback_state == PlaybackState.PLAYING && _playback_duration_ticks == 0:
		_finish_playback()


func is_recording() -> bool:
	return current_mode == ReplayMode.RECORDING


func is_playing() -> bool:
	return current_mode == ReplayMode.PLAYBACK && playback_state == PlaybackState.PLAYING


func should_suppress_live_actions() -> bool:
	return current_mode == ReplayMode.PLAYBACK


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
	if current_mode != ReplayMode.RECORDING:
		return ""

	var saved_replay_id: String = _save_replay()
	if saved_replay_id.is_empty():
		return ""

	# Keep the saved replay immutable while recording continues. Periodic state
	# files use the active replay ID, so carry them into the next snapshot's
	# namespace before rotating the ID.
	var next_replay_id: String = _generate_replay_id()
	_copy_replay_state_files(saved_replay_id, next_replay_id)
	current_replay_file = next_replay_id

	return saved_replay_id

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
		_last_checksum_tick = _get_current_tick()
		# A derived replay has no valid checksum files for its inherited prefix.
		# Resume verification only at the recorded derived-state boundary.
		if current_tick >= _verification_start_tick && is_checksum_available:
			verify_replay_state_at_tick(current_tick)

	# The final recorded tick must update the world before the SceneTree is paused
	# by the FINISHED callback, so complete when this tick reaches the duration.
	var duration_reached: bool = current_tick + 1 >= _playback_duration_ticks
	if duration_reached && _playback_tick >= _playback_actions.size():
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


func _copy_replay_state_files(source_replay_id: String, target_replay_id: String):
	var dir: DirAccess = DirAccess.open(STATE_DIR)
	if dir == null:
		return

	var source_prefix: String = source_replay_id + "-"
	dir.list_dir_begin()
	var file_name: String = dir.get_next()
	while !file_name.is_empty():
		if !dir.current_is_dir() && file_name.begins_with(source_prefix) && file_name.ends_with(".json"):
			var target_file_name: String = target_replay_id + file_name.trim_prefix(source_replay_id)
			var copy_error: Error = DirAccess.copy_absolute(STATE_DIR + file_name, STATE_DIR + target_file_name)
			if copy_error != OK:
				push_warning("Failed to copy replay state file %s (error %d)." % [file_name, copy_error])

		file_name = dir.get_next()
	dir.list_dir_end()


func _save_replay() -> String:
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

		if !_save_replay_metadata():
			return ""

		replay_saved.emit(current_replay_file)
		return current_replay_file

	return ""


func _execute_replay_action(action_data: Dictionary):
	var action_copy: Dictionary = action_data.duplicate()
	action_copy.erase("tick")

	# JSON-based legacy tools can stringify integer keys. Binary replay files keep
	# them as integers, but normalizing here preserves compatibility with both.
	var action: Dictionary = {}
	for key in action_copy.keys():
		action[int(key)] = action_copy[key]

	var action_type: Action.Type = action.get(Action.Field.TYPE, Action.Type.NONE)
	if !Action.is_replayable_type(action_type):
		return

	var game_client: GameClient = _get_game_client()
	if is_instance_valid(game_client):
		game_client.execute_replay_action(action)


func _finish_playback():
	if playback_state == PlaybackState.FINISHED:
		return

	playback_state = PlaybackState.FINISHED
	playback_state_changed.emit(playback_state)

	# Natural completion hands the reached game state to the player. The
	# FINISHED signal is emitted first so the UI can report completion and pause
	# before the mode transitions to recording.
	if !branch_recording_from_playback():
		push_error("Failed to transfer control after replay completion.")


func _load_replay_file(replay_id: String) -> Dictionary:
	# Load metadata first
	var metadata_file: String = REPLAY_DIR + replay_id + ".json"
	var metadata_content: String = FileAccess.get_file_as_string(metadata_file)
	var parsed_metadata: Variant = JSON.parse_string(metadata_content)

	if typeof(parsed_metadata) != TYPE_DICTIONARY:
		return {}
	var metadata: Dictionary = parsed_metadata

	# Load actions from binary file
	var actions: Array = []
	var binary_file: String = REPLAY_DIR + replay_id + ".bin"
	if !FileAccess.file_exists(binary_file):
		return {}

	var file: FileAccess = FileAccess.open(binary_file, FileAccess.READ)
	if file == null:
		return {}

	var action_count: int = file.get_32()
	var previous_tick: int = -1
	for _index in range(action_count):
		var action: Variant = file.get_var()
		if typeof(action) != TYPE_DICTIONARY:
			file.close()
			return {}

		var action_tick: int = action.get("tick", -1)
		if action_tick < previous_tick:
			file.close()
			return {}

		previous_tick = action_tick
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

	var last_tick: int = actions[-1].get("tick", 0)

	return (last_tick + 1) / 30  # Convert ticks to seconds


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
	_initial_game_state = initial_state.duplicate(true)

	_restore_exp_password(initial_state.get("exp_password", ""))
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
	if !_settings_before_playback.is_empty():
		_restore_exp_password(_settings_before_playback.get("exp_password", ""))
		_restore_wisdom_upgrades(_settings_before_playback.get("wisdom_upgrades", {}))
		Settings.flush()

	_clear_session_state()


func _clear_session_state():
	current_mode = ReplayMode.NONE
	playback_state = PlaybackState.STOPPED
	current_replay_file = ""

	_recorded_actions.clear()
	_recording_start_tick = 0
	_last_checksum_tick = 0

	_playback_actions.clear()
	_playback_tick = 0
	_playback_duration_ticks = 0
	_parent_replay_id = ""
	_branch_tick = -1
	_verification_start_tick = 0
	_initial_game_state.clear()
	_settings_before_playback.clear()
	_checksum_period = 300
	_detailed_checksums_enabled = true
	_state_verifier.set_detailed_checksums_enabled(_detailed_checksums_enabled)
	
	_game_client = null
	_state_verifier._game_client = null


func _serialize_static_var_states() -> Dictionary:
	return {
		"ItemContainerUidMax": UidMaxTracker.get_uid_max(UidMaxTracker.Type.ITEM_CONTAINER),
		"ItemUidMax": UidMaxTracker.get_uid_max(UidMaxTracker.Type.ITEM),
		"AutocastUidMax": UidMaxTracker.get_uid_max(UidMaxTracker.Type.AUTOCAST),
		"UnitUidMax": UidMaxTracker.get_uid_max(UidMaxTracker.Type.UNIT),
		"ProjectileUidMax": UidMaxTracker.get_uid_max(UidMaxTracker.Type.PROJECTILE),
		"ManualTimerUidMax": UidMaxTracker.get_uid_max(UidMaxTracker.Type.MANUAL_TIMER),
	}


func _restore_static_var_states(static_var_states: Dictionary):
	UidMaxTracker.reset()
	_restore_uid_max(UidMaxTracker.Type.ITEM_CONTAINER, static_var_states.get("ItemContainerUidMax", 1))
	_restore_uid_max(UidMaxTracker.Type.ITEM, static_var_states.get("ItemUidMax", 1))
	_restore_uid_max(UidMaxTracker.Type.AUTOCAST, static_var_states.get("AutocastUidMax", 1))
	_restore_uid_max(UidMaxTracker.Type.UNIT, static_var_states.get("UnitUidMax", 1))
	_restore_uid_max(UidMaxTracker.Type.PROJECTILE, static_var_states.get("ProjectileUidMax", 1))
	_restore_uid_max(UidMaxTracker.Type.MANUAL_TIMER, static_var_states.get("ManualTimerUidMax", 1))


func _restore_uid_max(type: UidMaxTracker.Type, target_uid_max: int):
	for _unused in range(1, maxi(target_uid_max, 1)):
		UidMaxTracker.get_uid_max_and_increment(type)


func _serialize_globals() -> Dictionary:
	return {
		"origin_seed": Globals.get_origin_seed(),
		"wave_count": Globals.get_wave_count(),
		"difficulty": Globals.get_difficulty(),
		"game_mode": Globals.get_game_mode(),
		"team_mode": Globals.get_team_mode(),
		"peer_id_list": Globals.get_game_peer_id_list().duplicate(),
		"player_name_map": Globals._enet_peer_id_to_player_name.duplicate(true),
	}


func _serialize_wisdom_upgrades() -> Dictionary:
	return Settings.get_wisdom_upgrades()


func _restore_exp_password(exp_password: String):
	Settings.set_setting(Settings.EXP_PASSWORD, exp_password)
	Settings.flush()

func _restore_globals(globals_data: Dictionary):
	Globals._origin_seed = globals_data.get("origin_seed", 0)
	Globals._wave_count = globals_data.get("wave_count", Globals.get_wave_count())
	Globals._difficulty = globals_data.get("difficulty", Globals.get_difficulty())
	Globals._game_mode = globals_data.get("game_mode", Globals.get_game_mode())
	Globals._team_mode = globals_data.get("team_mode", Globals.get_team_mode())
	Globals._game_peer_id_list = globals_data.get("peer_id_list", []).duplicate()

	# JSON object keys are strings, while runtime peer IDs are integers.
	var recorded_player_name_map: Dictionary = globals_data.get("player_name_map", {})
	var normalized_player_name_map: Dictionary = {}
	for peer_id in recorded_player_name_map:
		normalized_player_name_map[int(peer_id)] = recorded_player_name_map[peer_id]
	Globals._enet_peer_id_to_player_name = normalized_player_name_map


func _restore_wisdom_upgrades(upgrades_data: Dictionary):
	Settings.set_setting(Settings.WISDOM_UPGRADES_CACHED, upgrades_data)


func _generate_replay_id() -> String:
	var timestamp: String = str(Time.get_unix_time_from_system()).replace(".", "_")
	var candidate: String = "replay_%s_%d" % [timestamp, Time.get_ticks_usec()]
	var suffix: int = 1
	while FileAccess.file_exists(REPLAY_DIR + candidate + ".json") || FileAccess.file_exists(REPLAY_DIR + candidate + ".bin"):
		candidate = "replay_%s_%d_%d" % [timestamp, Time.get_ticks_usec(), suffix]
		suffix += 1
	return candidate


func _save_replay_metadata() -> bool:
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
		"parent_replay_id": _parent_replay_id,
		"branch_tick": _branch_tick,
		"verification_start_tick": _verification_start_tick,
	}

	var metadata_file: String = REPLAY_DIR + current_replay_file + ".json"
	var file: FileAccess = FileAccess.open(metadata_file, FileAccess.WRITE)
	if file == null:
		return false

	file.store_string(JSON.stringify(metadata, "\t"))
	file.close()
	return true


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
