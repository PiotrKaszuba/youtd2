class_name ReplayLogger extends Node


# Handles logging of game actions and state for replay functionality.
# Stores actions in JSONL format and periodic state dumps in JSON format.


signal replay_saved(file_path: String)
signal replay_save_failed(error_message: String)


const REPLAY_DIR: String = "user://replays"
const STATE_DIR: String = "user://replays/_state"
const DEFAULT_CHECKSUM_FREQUENCY: int = 300  # Every 10 seconds at 30fps


var _is_logging: bool = false
var _replay_id: String = ""
var _action_log: Array[Dictionary] = []
var _initial_state: Dictionary = {}
var _game_settings: Dictionary = {}
var _checksum_frequency: int = DEFAULT_CHECKSUM_FREQUENCY
var _last_checksum_tick: int = -1


#########################
###     Built-in      ###
#########################

func _ready():
	# Ensure replay directories exist
	_ensure_directories_exist()


#########################
###       Public      ###
#########################

func start_logging(replay_id: String = "") -> bool:
	if _is_logging:
		push_error("Replay logging already started")
		return false
	
	if replay_id.is_empty():
		replay_id = _generate_replay_id()
	
	_replay_id = replay_id
	_is_logging = true
	_action_log.clear()
	_last_checksum_tick = -1
	
	# Capture initial state
	_capture_initial_state()
	_capture_game_settings()
	
	print_verbose("Started replay logging with ID: ", _replay_id)
	return true


func stop_logging() -> bool:
	if !_is_logging:
		push_error("Replay logging not started")
		return false
	
	_is_logging = false
	print_verbose("Stopped replay logging")
	return true


func log_action(action: Dictionary, tick: int):
	if !_is_logging:
		return
	
	var log_entry = {
		"tick": tick,
		"action": action,
		"timestamp": Time.get_ticks_msec()
	}
	
	_action_log.append(log_entry)
	
	# Check if we need to dump state
	if tick - _last_checksum_tick >= _checksum_frequency:
		_dump_state_at_tick(tick)
		_last_checksum_tick = tick


func save_replay() -> bool:
	if !_is_logging:
		push_error("Cannot save replay - logging not started")
		replay_save_failed.emit("Logging not started")
		return false
	
	var replay_file_path = REPLAY_DIR + "/" + _replay_id + ".jsonl"
	
	var file = FileAccess.open(replay_file_path, FileAccess.WRITE)
	if file == null:
		var error_msg = "Failed to open replay file: " + replay_file_path
		push_error(error_msg)
		replay_save_failed.emit(error_msg)
		return false
	
	# Write metadata header
	var metadata = {
		"version": "1.0",
		"replay_id": _replay_id,
		"created_at": Time.get_datetime_string_from_system(),
		"initial_state": _initial_state,
		"game_settings": _game_settings,
		"action_count": _action_log.size()
	}
	
	file.store_line(JSON.stringify(metadata))
	
	# Write actions in JSONL format
	for action_entry in _action_log:
		file.store_line(JSON.stringify(action_entry))
	
	file.close()
	
	print_verbose("Saved replay to: ", replay_file_path)
	replay_saved.emit(replay_file_path)
	return true


func set_checksum_frequency(frequency: int):
	_checksum_frequency = max(1, frequency)


func get_checksum_frequency() -> int:
	return _checksum_frequency


func is_logging() -> bool:
	return _is_logging


func get_replay_id() -> String:
	return _replay_id


#########################
###      Private      ###
#########################

func _ensure_directories_exist():
	var dir = DirAccess.open("user://")
	if dir == null:
		push_error("Failed to access user directory")
		return
	
	# Create replays directory
	if !dir.dir_exists(REPLAY_DIR):
		dir.make_dir(REPLAY_DIR)
	
	# Create state directory
	if !dir.dir_exists(STATE_DIR):
		dir.make_dir(STATE_DIR)


func _generate_replay_id() -> String:
	var timestamp = Time.get_unix_time_from_system()
	var random_suffix = randi() % 10000
	return "replay_%d_%04d" % [timestamp, random_suffix]


func _capture_initial_state():
	_initial_state = {
		"game_mode": Globals.get_game_mode(),
		"difficulty": Globals.get_difficulty(),
		"wave_count": Globals.get_wave_count(),
		"origin_seed": Globals._origin_seed,
		"rng_seed": Globals.synced_rng.get_seed(),
		"rng_state": Globals.synced_rng.get_state(),
		"player_count": PlayerManager.get_player_list().size(),
		"map_name": _get_map_name()
	}


func _capture_game_settings():
	_game_settings = {
		"player_mode": Globals.get_player_mode(),
		"team_mode": Globals.get_team_mode(),
		"update_ticks_per_physics_tick": Globals.get_update_ticks_per_physics_tick()
	}


func _get_map_name() -> String:
	var map = Globals._map
	if map == null:
		return "unknown"
	
	# Try to get map name from scene file
	var scene_file = map.scene_file_path
	if scene_file.is_empty():
		return "unknown"
	
	var file_name = scene_file.get_file()
	return file_name.get_basename()


func _dump_state_at_tick(tick: int):
	var state_file_path = STATE_DIR + "/" + _replay_id + "-" + str(tick) + ".json"
	
	var state_data = {
		"tick": tick,
		"timestamp": Time.get_ticks_msec(),
		"checksum": _calculate_game_state_checksum(),
		"state_tree": _calculate_state_tree()
	}
	
	var file = FileAccess.open(state_file_path, FileAccess.WRITE)
	if file == null:
		push_error("Failed to open state file: " + state_file_path)
		return
	
	file.store_string(JSON.stringify(state_data, "\t"))
	file.close()
	
	print_verbose("Dumped state at tick ", tick, " to: ", state_file_path)


func _calculate_game_state_checksum() -> String:
	var ctx = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	
	var state_data = PackedByteArray()
	
	# Add player states
	var player_list = PlayerManager.get_player_list()
	for player in player_list:
		state_data.append_array(_serialize_player_state(player))
	
	# Add tower states
	var tower_list = Utils.get_tower_list()
	for tower in tower_list:
		state_data.append_array(_serialize_tower_state(tower))
	
	# Add creep states
	var creep_list = Utils.get_creep_list()
	for creep in creep_list:
		state_data.append_array(_serialize_creep_state(creep))
	
	# Add item states
	var item_list = get_tree().get_nodes_in_group("items")
	for item in item_list:
		state_data.append_array(_serialize_item_state(item))
	
	# Add RNG state
	state_data.append_array(_int_to_bytes(Globals.synced_rng.get_seed()))
	state_data.append_array(_int_to_bytes(Globals.synced_rng.get_state()))
	
	ctx.update(state_data)
	return ctx.finish().hex_encode()


func _calculate_state_tree() -> Dictionary:
	return {
		"players": _calculate_player_checksums(),
		"towers": _calculate_tower_checksums(),
		"creeps": _calculate_creep_checksums(),
		"items": _calculate_item_checksums(),
		"rng_state": {
			"seed": Globals.synced_rng.get_seed(),
			"state": Globals.synced_rng.get_state()
		}
	}


func _calculate_player_checksums() -> Dictionary:
	var player_checksums = {}
	var player_list = PlayerManager.get_player_list()
	
	for player in player_list:
		var player_id = player.get_id()
		player_checksums[str(player_id)] = {
			"checksum": _calculate_player_state_checksum(player),
			"name": player.get_player_name(),
			"gold": player.get_gold(),
			"tomes": player.get_tomes(),
			"level": player.get_team().get_level()
		}
	
	return player_checksums


func _calculate_tower_checksums() -> Dictionary:
	var tower_checksums = {}
	var tower_list = Utils.get_tower_list()
	
	for tower in tower_list:
		var tower_id = _get_tower_identifier(tower)
		tower_checksums[tower_id] = {
			"checksum": _calculate_tower_state_checksum(tower),
			"name": tower.get_display_name(),
			"position": tower.get_position_wc3(),
			"player_id": tower.get_player().get_id(),
			"level": tower.get_level(),
			"experience": tower.get_experience()
		}
	
	return tower_checksums


func _calculate_creep_checksums() -> Dictionary:
	var creep_checksums = {}
	var creep_list = Utils.get_creep_list()
	
	for creep in creep_list:
		var creep_id = _get_creep_identifier(creep)
		creep_checksums[creep_id] = {
			"checksum": _calculate_creep_state_checksum(creep),
			"name": creep.get_display_name(),
			"position": creep.get_position_wc3(),
			"health": creep.get_health(),
			"level": creep.get_level()
		}
	
	return creep_checksums


func _calculate_item_checksums() -> Dictionary:
	var item_checksums = {}
	var item_list = get_tree().get_nodes_in_group("items")
	
	for item in item_list:
		var item_id = _get_item_identifier(item)
		item_checksums[item_id] = {
			"checksum": _calculate_item_state_checksum(item),
			"name": item.get_display_name(),
			"player_id": item.get_player().get_id(),
			"charges": item.get_charge_count()
		}
	
	return item_checksums


func _get_tower_identifier(tower: Tower) -> String:
	return str(tower.get_player().get_id()) + "_" + str(tower.get_position_wc3())


func _get_creep_identifier(creep: Creep) -> String:
	return str(creep.get_uid()) + "_" + str(creep.get_position_wc3())


func _get_item_identifier(item: Item) -> String:
	return str(item.get_player().get_id()) + "_" + str(item.get_uid())


func _serialize_player_state(player: Player) -> PackedByteArray:
	var data = PackedByteArray()
	data.append_array(_float_to_bytes(player.get_gold()))
	data.append_array(_int_to_bytes(player.get_tomes()))
	data.append_array(_int_to_bytes(player.get_id()))
	data.append_array(_float_to_bytes(player.get_total_damage()))
	data.append_array(_float_to_bytes(player.get_gold_farmed()))
	return data


func _serialize_tower_state(tower: Tower) -> PackedByteArray:
	var data = PackedByteArray()
	data.append_array(_int_to_bytes(tower.get_id()))
	data.append_array(_int_to_bytes(tower.get_level()))
	data.append_array(_float_to_bytes(tower.get_experience()))
	data.append_array(_float_to_bytes(tower.get_health()))
	data.append_array(_float_to_bytes(tower.get_mana()))
	data.append_array(_float_to_bytes(tower.get_attack_damage_dealt()))
	data.append_array(_float_to_bytes(tower.get_spell_damage_dealt()))
	data.append_array(_int_to_bytes(tower.get_kill_count()))
	data.append_array(_int_to_bytes(tower.get_uid()))
	return data


func _serialize_creep_state(creep: Creep) -> PackedByteArray:
	var data = PackedByteArray()
	data.append_array(_int_to_bytes(creep.get_id()))
	data.append_array(_int_to_bytes(creep.get_level()))
	data.append_array(_float_to_bytes(creep.get_health()))
	data.append_array(_float_to_bytes(creep.get_mana()))
	data.append_array(_int_to_bytes(creep.get_uid()))
	return data


func _serialize_item_state(item: Item) -> PackedByteArray:
	var data = PackedByteArray()
	data.append_array(_int_to_bytes(item.get_id()))
	data.append_array(_int_to_bytes(item.get_charge_count()))
	data.append_array(_int_to_bytes(item.get_uid()))
	return data


func _calculate_player_state_checksum(player: Player) -> String:
	var ctx = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(_serialize_player_state(player))
	return ctx.finish().hex_encode()


func _calculate_tower_state_checksum(tower: Tower) -> String:
	var ctx = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(_serialize_tower_state(tower))
	return ctx.finish().hex_encode()


func _calculate_creep_state_checksum(creep: Creep) -> String:
	var ctx = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(_serialize_creep_state(creep))
	return ctx.finish().hex_encode()


func _calculate_item_state_checksum(item: Item) -> String:
	var ctx = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(_serialize_item_state(item))
	return ctx.finish().hex_encode()


func _float_to_bytes(value: float) -> PackedByteArray:
	var bytes = PackedByteArray()
	bytes.resize(4)
	bytes.encode_float(0, value)
	return bytes


func _int_to_bytes(value: int) -> PackedByteArray:
	var bytes = PackedByteArray()
	bytes.resize(4)
	bytes.encode_s32(0, value)
	return bytes
