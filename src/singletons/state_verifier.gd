class_name StateVerifier extends Node


# Handles verification of game state consistency using SHA-256 checksums.
# Provides hierarchical verification with detailed per-entity checksums.


signal verification_completed(result: Dictionary)
signal verification_failed(error_message: String)


var _is_verifying: bool = false
var _verification_data: Dictionary = {}


#########################
###       Public      ###
#########################

func verify_state_at_tick(tick: int, replay_id: String) -> bool:
	if _is_verifying:
		push_error("State verification already in progress")
		return false
	
	var state_file_path = "user://replays/_state/" + replay_id + "-" + str(tick) + ".json"
	
	var file = FileAccess.open(state_file_path, FileAccess.READ)
	if file == null:
		var error_msg = "Failed to open state file: " + state_file_path
		push_error(error_msg)
		verification_failed.emit(error_msg)
		return false
	
	var json_string = file.get_as_text()
	file.close()
	
	var state_data = JSON.parse_string(json_string)
	if state_data == null:
		var error_msg = "Failed to parse state file: " + state_file_path
		push_error(error_msg)
		verification_failed.emit(error_msg)
		return false
	
	_is_verifying = true
	_verification_data = state_data
	
	# Perform verification
	var result = _perform_verification()
	
	_is_verifying = false
	
	if result["success"]:
		verification_completed.emit(result)
	else:
		verification_failed.emit(result["error_message"])
	
	return result["success"]


func calculate_current_state_checksum() -> String:
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


func get_state_tree() -> Dictionary:
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


#########################
###      Private      ###
#########################

func _perform_verification() -> Dictionary:
	var result = {
		"success": false,
		"error_message": "",
		"differences": []
	}
	
	# Calculate current state checksum
	var current_checksum = calculate_current_state_checksum()
	var expected_checksum = _verification_data.get("checksum", "")
	
	if current_checksum == expected_checksum:
		result["success"] = true
		return result
	
	# Checksums don't match, perform detailed verification
	result["error_message"] = "State checksum mismatch at tick " + str(_verification_data.get("tick", 0))
	
	# Compare state trees
	var current_tree = get_state_tree()
	var expected_tree = _verification_data.get("state_tree", {})
	
	var differences = _compare_state_trees(current_tree, expected_tree, "")
	result["differences"] = differences
	
	return result


func _compare_state_trees(current: Dictionary, expected: Dictionary, path: String) -> Array:
	var differences = []
	
	# Check for missing keys in current
	for key in expected.keys():
		if !current.has(key):
			differences.append({
				"path": path + "." + key,
				"type": "missing",
				"expected": expected[key],
				"current": null
			})
	
	# Check for extra keys in current
	for key in current.keys():
		if !expected.has(key):
			differences.append({
				"path": path + "." + key,
				"type": "extra",
				"expected": null,
				"current": current[key]
			})
	
	# Check for value differences
	for key in current.keys():
		if expected.has(key):
			var current_value = current[key]
			var expected_value = expected[key]
			
			if current_value is Dictionary && expected_value is Dictionary:
				# Recursively compare dictionaries
				var sub_differences = _compare_state_trees(current_value, expected_value, path + "." + key)
				differences.append_array(sub_differences)
			elif current_value != expected_value:
				differences.append({
					"path": path + "." + key,
					"type": "different",
					"expected": expected_value,
					"current": current_value
				})
	
	return differences


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
