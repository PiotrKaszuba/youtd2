class_name ReplayRecorder
extends Node


# Records meta and timeslots to JSONL, requests periodic state snapshots.


var _replay_id: String = ""
var _file: FileAccess = null
var _checksum_period_ticks: int = 300
var _enabled: bool = true
var _seed: int = 0


func setup(replay_id: String, seed: int, checksum_period_ticks: int):
	ReplayTypes.ensure_dirs_exist()
	_replay_id = replay_id
	_seed = seed
	_checksum_period_ticks = checksum_period_ticks
	var path: String = ReplayTypes.get_replay_file_path(_replay_id)
	_file = FileAccess.open(path, FileAccess.WRITE)
	if _file == null:
		push_error("ReplayRecorder failed to open file: %s" % path)
		_enabled = false
		return
	_write_meta_line()


func is_enabled() -> bool:
	return _enabled


func close():
	if _file != null:
		_file.flush()
		_file.close()
		_file = null


func record_timeslot(tick: int, timeslot: Array):
	if !_enabled || _file == null:
		return

	# Filter actions
	var filtered: Array = []
	for action in timeslot:
		if ReplayTypes.action_is_loggable(action):
			filtered.append(action)

	var line_dict: Dictionary = {
		"type": "timeslot",
		"tick": tick,
		"actions": filtered,
	}

	var should_snapshot: bool = (tick % _checksum_period_ticks) == 0
	if should_snapshot:
		var snapshot: Dictionary = StateSnapshotter.build_snapshot_dict()
		var root_hex: String = snapshot.get("root", "")
		var state_path: String = ReplayTypes.get_state_file_path(_replay_id, tick)
		var state_file: FileAccess = FileAccess.open(state_path, FileAccess.WRITE)
		if state_file != null:
			state_file.store_string(JSON.stringify(snapshot, "\t"))
			state_file.close()
			line_dict["root_checksum"] = root_hex
			line_dict["state_file"] = state_path.get_file()

	_file.store_string(JSON.stringify(line_dict) + "\n")


func _write_meta_line():
	if !_enabled || _file == null:
		return

	var settings_dict: Dictionary = {
		"game_mode": int(Globals.get_game_mode()),
		"difficulty": int(Globals.get_difficulty()),
		"team_mode": int(Globals.get_team_mode()),
		"wave_count": int(Globals.get_wave_count()),
	}

	var header: Dictionary = {
		"type": "meta",
		"version": ReplayTypes.SCHEMA_VERSION,
		"created_at": Time.get_unix_time_from_system(),
		"seed": _seed,
		"settings": settings_dict,
		"checksum_period": _checksum_period_ticks,
		"state_dir": ReplayTypes.STATE_DIR_NAME,
	}

	_file.store_string(JSON.stringify(header) + "\n")


