class_name ReplayService
extends Node


enum Mode {
	IDLE,
	RECORDING,
	PLAYBACK,
}


const META_LINE_TYPE: String = "meta"
const TIMESLOT_LINE_TYPE: String = "timeslot"
const REPLAY_DIR: String = "user://replays/"
const REPLAY_STATE_DIR: String = "user://replays/_state/"
const PASSWORD_BACKUP_SUFFIX: String = "-before-password.bak"
const DEFAULT_VERSION: int = 1


var _mode: Mode = Mode.IDLE
var _record_meta: Dictionary = {}
var _record_timeslot_list: Array = []
var _record_checkpoint_map: Dictionary = {}
var _prepared_replay_path: String = ""
var _prepared_replay_meta: Dictionary = {}
var _playback_timeslot_map: Dictionary = {}
var _playback_tick_list: Array[int] = []
var _playback_index: int = 0
var _playback_finished: bool = false
var _password_backup_path: String = ""
var _chat_reports_enabled: bool = true


#########################
###     Built-in      ###
#########################

func _ready():
	_chat_reports_enabled = Config.replay_chat_reports_enabled()


#########################
###       Public      ###
#########################

func prepare_recording(meta: Dictionary):
	_mode = Mode.RECORDING
	_record_meta = meta.duplicate(true)
	_record_meta["version"] = DEFAULT_VERSION
	_record_timeslot_list.clear()
	_record_checkpoint_map.clear()
	_playback_timeslot_map.clear()
	_playback_tick_list.clear()
	_playback_index = 0
	_playback_finished = false
	_prepared_replay_path = ""
	_prepared_replay_meta.clear()
	_password_backup_path = ""


func is_recording() -> bool:
	return _mode == Mode.RECORDING


func record_timeslot(tick: int, timeslot: Array):
	if _mode != Mode.RECORDING:
		return

	var entry: Dictionary = {
		"tick": tick,
		"actions": timeslot.duplicate(true),
	}

	_record_timeslot_list.append(entry)


func record_checkpoint(tick: int, checkpoint: Dictionary):
	if _mode != Mode.RECORDING:
		return

	_record_checkpoint_map[tick] = checkpoint.duplicate(true)


func export_to_disk(current_tick: int) -> String:
	if _mode != Mode.RECORDING:
		return ""

	var export_id: String = _make_replay_id()
	var replay_path: String = "%s%s.jsonl" % [REPLAY_DIR, export_id]

	_ensure_directory(REPLAY_DIR)
	_ensure_directory(REPLAY_STATE_DIR)

	var file: FileAccess = FileAccess.open(replay_path, FileAccess.WRITE)
	if file == null:
		push_error("Failed to open replay file for writing: %s" % replay_path)
		return ""

	var header: Dictionary = _record_meta.duplicate(true)
	header["type"] = META_LINE_TYPE
	header["replay_id"] = export_id
	header["exported_at"] = Time.get_datetime_string_from_system(false)
	header["exported_tick"] = current_tick

	file.store_line(JSON.stringify(header))

	for entry in _record_timeslot_list:
		var tick: int = entry["tick"]
		if tick > current_tick:
			break

		var payload: Dictionary = {
			"type": TIMESLOT_LINE_TYPE,
			"tick": tick,
			"actions": _encode_actions(entry["actions"]),
		}

		if _record_checkpoint_map.has(tick):
			var checkpoint: Dictionary = _record_checkpoint_map[tick]
			var state_path: String = "%s%s-%d.json" % [REPLAY_STATE_DIR, export_id, tick]
			_write_checkpoint_file(state_path, checkpoint)
			payload["state_path"] = state_path

		file.store_line(JSON.stringify(payload))

	file.close()

	return replay_path


func prepare_playback(replay_path: String) -> bool:
	var file: FileAccess = FileAccess.open(replay_path, FileAccess.READ)
	if file == null:
		push_error("Failed to open replay for playback: %s" % replay_path)
		return false

	_prepared_replay_path = ""
	_prepared_replay_meta.clear()
	_playback_timeslot_map.clear()
	_playback_tick_list.clear()
	_playback_index = 0
	_playback_finished = false

	while file.get_position() < file.get_length():
		var line: String = file.get_line()
		if line.is_empty():
			continue

		var parsed: Variant = JSON.parse_string(line)
		if typeof(parsed) != TYPE_DICTIONARY:
			push_warning("Ignoring malformed replay line.")
			continue

		var dict: Dictionary = parsed
		var line_type: String = dict.get("type", "")

		match line_type:
			META_LINE_TYPE:
				_prepared_replay_meta = dict.duplicate(true)
			TIMESLOT_LINE_TYPE:
				var tick: int = dict.get("tick", -1)
				if tick < 0:
					continue

				var encoded_actions: String = dict.get("actions", "")
				var actions: Array = _decode_actions(encoded_actions)
				_playback_timeslot_map[tick] = {
					"actions": actions,
					"state_path": dict.get("state_path", ""),
				}
				_playback_tick_list.append(tick)
			_:
				continue

	file.close()

	_playback_tick_list.sort()

	var success: bool = !_prepared_replay_meta.is_empty()

	if success:
		_prepared_replay_path = replay_path
	else:
		_prepared_replay_path = ""

	return success


func has_prepared_playback() -> bool:
	return !_prepared_replay_path.is_empty()


func get_prepared_replay_meta() -> Dictionary:
	return _prepared_replay_meta.duplicate(true)


func begin_playback():
	if !has_prepared_playback():
		return

	_mode = Mode.PLAYBACK
	_playback_index = 0
	_playback_finished = false


func is_playback_active() -> bool:
	return _mode == Mode.PLAYBACK && !_playback_finished


func should_block_actions() -> bool:
	return is_playback_active()


func get_timeslot_for_tick(tick: int) -> Array:
	if !is_playback_active():
		return []

	if !_playback_timeslot_map.has(tick):
		_finish_playback()
		return []

	var entry: Dictionary = _playback_timeslot_map[tick]
	var actions: Array = entry.get("actions", []).duplicate(true)

	if _playback_index < _playback_tick_list.size() && _playback_tick_list[_playback_index] == tick:
		_playback_index += 1
		if _playback_index >= _playback_tick_list.size():
			_playback_finished = true

	return actions


func get_state_path_for_tick(tick: int) -> String:
	if !is_playback_active():
		return ""

	if !_playback_timeslot_map.has(tick):
		return ""

	var entry: Dictionary = _playback_timeslot_map[tick]
	var state_path: String = entry.get("state_path", "")

	return state_path


func finish_playback_and_restore():
	_finish_playback()
	_restore_password_backup()


func clear_prepared_replay():
	_prepared_replay_path = ""
	_prepared_replay_meta.clear()


func chat_reports_enabled() -> bool:
	return _chat_reports_enabled


func make_password_backup(replay_id: String):
	var exp_password: String = Settings.get_setting(Settings.EXP_PASSWORD)
	var wisdom_upgrades: Dictionary = Settings.get_setting(Settings.WISDOM_UPGRADES_CACHED)
	var payload: Dictionary = {
		"exp_password": exp_password,
		"wisdom_upgrades": wisdom_upgrades,
	}

	_ensure_directory(REPLAY_STATE_DIR)
	var backup_path: String = "%s%s%s" % [REPLAY_STATE_DIR, replay_id, PASSWORD_BACKUP_SUFFIX]
	var file: FileAccess = FileAccess.open(backup_path, FileAccess.WRITE)
	if file != null:
		file.store_line(JSON.stringify(payload))
		file.close()

	_password_backup_path = backup_path


func apply_replay_settings(meta: Dictionary):
	var new_password: String = meta.get("exp_password", "")
	var new_upgrades: Dictionary = meta.get("wisdom_upgrades", {})

	if new_password is String:
		Settings.set_setting(Settings.EXP_PASSWORD, new_password)

	if new_upgrades is Dictionary:
		Settings.set_setting(Settings.WISDOM_UPGRADES_CACHED, new_upgrades)

	Settings.flush()


#########################
###      Private      ###
#########################

func _finish_playback():
	_playback_finished = true
	if _mode == Mode.PLAYBACK:
		_mode = Mode.IDLE


func _restore_password_backup():
	if _password_backup_path.is_empty():
		return

	var file: FileAccess = FileAccess.open(_password_backup_path, FileAccess.READ)
	if file == null:
		return

	var line: String = file.get_line()
	file.close()

	var parsed: Variant = JSON.parse_string(line)
	if typeof(parsed) != TYPE_DICTIONARY:
		return

	var dict: Dictionary = parsed
	var exp_password: String = dict.get("exp_password", Settings.get_setting(Settings.EXP_PASSWORD))
	var wisdom_upgrades: Dictionary = dict.get("wisdom_upgrades", Settings.get_setting(Settings.WISDOM_UPGRADES_CACHED))

	Settings.set_setting(Settings.EXP_PASSWORD, exp_password)
	Settings.set_setting(Settings.WISDOM_UPGRADES_CACHED, wisdom_upgrades)
	Settings.flush()
	_password_backup_path = ""


func _encode_actions(timeslot: Array) -> String:
	var bytes: PackedByteArray = var_to_bytes(timeslot)
	var encoded: String = Marshalls.raw_to_base64(bytes)

	return encoded


func _decode_actions(encoded: String) -> Array:
	if encoded.is_empty():
		return []

	var bytes: PackedByteArray = Marshalls.base64_to_raw(encoded)
	var value: Variant = bytes_to_var(bytes)

	if typeof(value) == TYPE_ARRAY:
		return value

	return []


func _write_checkpoint_file(path: String, checkpoint: Dictionary):
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("Failed to open checkpoint file for writing: %s" % path)
		return

	file.store_line(JSON.stringify(checkpoint, "    "))
	file.close()


func _make_replay_id() -> String:
	var dt: Dictionary = Time.get_datetime_dict_from_system()
	var id: String = "%04d%02d%02d_%02d%02d%02d" % [
		dt["year"],
		dt["month"],
		dt["day"],
		dt["hour"],
		dt["minute"],
		dt["second"],
	]

	return id


func _ensure_directory(path: String):
	var dir: DirAccess = DirAccess.open(path)
	if dir == null:
		DirAccess.make_dir_recursive_absolute(path)
