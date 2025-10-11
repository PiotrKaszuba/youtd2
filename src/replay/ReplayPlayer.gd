class_name ReplayPlayer
extends Node


# Plays a recorded replay by feeding timeslots to GameClient.


var _path: String = ""
var _file: FileAccess = null
var _meta: Dictionary = {}
var _finished_meta: bool = false
var _waiting_tick: int = 0
var _game_client: GameClient
var _expected_root_by_tick: Dictionary = {}


func setup(path: String, game_client: GameClient):
	_path = path
	_game_client = game_client
	_file = FileAccess.open(path, FileAccess.READ)
	if _file == null:
		push_error("ReplayPlayer cannot open: %s" % path)
		return
	# Read meta
	if !_file.eof_reached():
		var meta_line: String = _file.get_line()
		_meta = JSON.parse_string(meta_line)
		_finished_meta = true
		# Seed RNG and stash settings
		if typeof(_meta) == TYPE_DICTIONARY:
			var seed: int = _meta.get("seed", 0)
			Globals.synced_rng.set_seed(seed)


func preload_timeslots_if_needed(current_tick: int):
	# Preload upcoming timeslots into client buffer so ticks can proceed
	if _file == null:
		return

	var to_send: Dictionary = {}
	var count: int = 0
	while !_file.eof_reached() && count < 32:
		var line: String = _file.get_line()
		if line.is_empty():
			continue
		var obj: Dictionary = JSON.parse_string(line)
		if typeof(obj) != TYPE_DICTIONARY:
			continue
		if obj.get("type", "") != "timeslot":
			continue
		var tick: int = obj.get("tick", -1)
		if tick < current_tick:
			continue
		var actions: Array = obj.get("actions", [])
		to_send[tick] = actions
		if obj.has("root_checksum"):
			_expected_root_by_tick[tick] = String(obj["root_checksum"]) 
		count += 1

	if !to_send.is_empty():
		_game_client.receive_timeslots(to_send)


func is_finished() -> bool:
	return _file == null || _file.eof_reached()


func get_expected_root_for_tick(tick: int) -> String:
	if _expected_root_by_tick.has(tick):
		return _expected_root_by_tick[tick]
	return ""


