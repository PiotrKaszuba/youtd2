class_name StateVerifier extends Node

# Handles comprehensive game state verification with checksum trees
# Creates hierarchical checksums for detailed state comparison

var _game_client: GameClient

# Configuration for checksum frequency and granularity
var _detailed_checksums_enabled: bool = true  # Enable per-entity detailed checksums

#########################
###       Public      ###
#########################

func set_detailed_checksums_enabled(enabled: bool) -> void:
	_detailed_checksums_enabled = enabled

func generate_checksum_tree() -> Dictionary:
	"""Generate a hierarchical checksum tree of the current game state"""

	var root_checksum: Dictionary = {
		"type": "root",
		"checksum": "",
		"children": {},
		"timestamp": Time.get_unix_time_from_system(),
	}

	# Generate checksums for different game systems
	root_checksum["children"]["globals"] = _generate_globals_checksum()

	if _detailed_checksums_enabled:
		root_checksum["children"]["players"] = _generate_players_checksum()
		root_checksum["children"]["towers"] = _generate_towers_checksum()
		root_checksum["children"]["creeps"] = _generate_creeps_checksum()
		root_checksum["children"]["items"] = _generate_items_checksum()
		# root_checksum["children"]["projectiles"] = _generate_projectiles_checksum()

	# Generate root checksum from all children
	root_checksum["checksum"] = _calculate_combined_checksum(root_checksum["children"])

	return root_checksum


func compare_states(state_a: Dictionary, state_b: Dictionary) -> Dictionary:
	"""Compare two state trees and return differences"""

	var differences: Dictionary = {
		"root_different": state_a.get("checksum") != state_b.get("checksum"),
		"differences": [],
	}

	_compare_tree_nodes(state_a, state_b, "", differences["differences"])

	return differences


func load_checksum_from_file(file_path: String) -> Dictionary:
	"""Load a checksum tree from a file"""
	if not FileAccess.file_exists(file_path):
		return {}

	var file_content: String = FileAccess.get_file_as_string(file_path)
	if file_content.is_empty():
		return {}

	var checksum_data: Dictionary = JSON.parse_string(file_content)
	return checksum_data if checksum_data else {}


func verify_against_recorded_state(recorded_checksum_path: String) -> Dictionary:
	"""Verify current state against a recorded checksum file"""
	var result: Dictionary = {
		"valid": true,
		"errors": [],
		"file_path": recorded_checksum_path
	}

	# Load the recorded checksum
	var recorded_checksum: Dictionary = load_checksum_from_file(recorded_checksum_path)
	if recorded_checksum.is_empty():
		result["errors"].append("Could not load recorded checksum from %s" % recorded_checksum_path)
		result["valid"] = false
		return result

	# Generate current state checksum
	var current_checksum: Dictionary = generate_checksum_tree()

	# Validate tree consistency
	var errors: Array = []
	_validate_tree_consistency(current_checksum, errors)

	# Compare the checksums
	var differences: Dictionary = compare_states(recorded_checksum, current_checksum)

	if differences.get("root_different", false) or not differences.get("differences", []).is_empty():
		result["valid"] = false
		result["differences"] = differences["differences"]
		result["recorded_checksum"] = recorded_checksum
		result["current_checksum"] = current_checksum

	return result


#########################
###      Private      ###
#########################

func _generate_globals_checksum() -> Dictionary:
	"""Generate checksum for global game state"""

	var globals_data: Dictionary = {
		"type": "globals",
		"origin_seed": Globals.get_origin_seed(),
		"wave_count": Globals.get_wave_count(),
		"difficulty": Globals.get_difficulty(),
		"game_mode": Globals.get_game_mode(),
		"team_mode": Globals.get_team_mode(),
		"current_tick": _get_current_tick(),
	}

	return {
		"type": "globals",
		"checksum": _calculate_node_checksum(globals_data),
		"data": globals_data,
	}


func _generate_players_checksum() -> Dictionary:
	"""Generate checksum for all players"""

	var player_checksums: Dictionary = {}

	var player_list: Array = PlayerManager.get_player_list()
	for player in player_list:
		var player_data: Dictionary = _get_player_data(player)
		player_checksums["player_%d" % player.get_id()] = {
			"type": "player",
			"checksum": _calculate_node_checksum(player_data),
			"data": player_data,
		}

	var combined_checksum: String = _calculate_combined_checksum(player_checksums)

	return {
		"type": "players",
		"checksum": combined_checksum,
		"children": player_checksums,
	}


func _generate_towers_checksum() -> Dictionary:
	"""Generate checksum for all towers"""

	var tower_checksums: Dictionary = {}

	var tower_list: Array = Utils.get_tower_list()
	for tower in tower_list:
		var tower_data: Dictionary = _get_tower_data(tower)
		tower_checksums["tower_%d" % tower.get_uid()] = {
			"type": "tower",
			"checksum": _calculate_node_checksum(tower_data),
			"data": tower_data,
		}

	var combined_checksum: String = _calculate_combined_checksum(tower_checksums)

	return {
		"type": "towers",
		"checksum": combined_checksum,
		"children": tower_checksums,
	}


func _generate_creeps_checksum() -> Dictionary:
	"""Generate checksum for all creeps"""

	var creep_checksums: Dictionary = {}

	var creep_list: Array = Utils.get_creep_list()
	for creep in creep_list:
		var creep_data: Dictionary = _get_creep_data(creep)
		creep_checksums["creep_%d" % creep.get_uid()] = {
			"type": "creep",
			"checksum": _calculate_node_checksum(creep_data),
			"data": creep_data,
		}

	var combined_checksum: String = _calculate_combined_checksum(creep_checksums)

	return {
		"type": "creeps",
		"checksum": combined_checksum,
		"children": creep_checksums,
	}


func _generate_items_checksum() -> Dictionary:
	"""Generate checksum for all items"""

	var item_checksums: Dictionary = {}

	# Get items from all players
	var player_list: Array = PlayerManager.get_player_list()
	for player in player_list:
		var item_stash: ItemContainer = player.get_item_stash()
		var horadric_stash: ItemContainer = player.get_horadric_stash()

		var items: Array = item_stash.get_item_list() + horadric_stash.get_item_list()
		for item in items:
			var item_data: Dictionary = _get_item_data(item)
			item_checksums["item_%d" % item.get_uid()] = {
				"type": "item",
				"checksum": _calculate_node_checksum(item_data),
				"data": item_data,
			}

	var combined_checksum: String = _calculate_combined_checksum(item_checksums)

	return {
		"type": "items",
		"checksum": combined_checksum,
		"children": item_checksums,
	}


# func _generate_projectiles_checksum() -> Dictionary:
# 	"""Generate checksum for all projectiles"""

# 	var projectile_checksums: Dictionary = {}

# 	var projectile_list: Array = get_tree().get_nodes_in_group("projectiles")
# 	for projectile in projectile_list:
# 		var projectile_data: Dictionary = _get_projectile_data(projectile)
# 		projectile_checksums["projectile_%d" % projectile.get_instance_id()] = {
# 			"type": "projectile",
# 			"checksum": _calculate_node_checksum(projectile_data),
# 			"data": projectile_data,
# 		}

# 	var combined_checksum: String = _calculate_combined_checksum(projectile_checksums)

# 	return {
# 		"type": "projectiles",
# 		"checksum": combined_checksum,
# 		"children": projectile_checksums,
# 	}


func _calculate_node_checksum(data: Dictionary) -> String:
	"""Calculate checksum for a single node"""

	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_MD5)

	var json_string: String = JSON.stringify(data)
	ctx.update(json_string.to_utf8_buffer())

	return ctx.finish().hex_encode()


func _calculate_combined_checksum(children: Dictionary) -> String:
	"""Calculate combined checksum from child nodes"""

	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)

	var combined_data: PackedByteArray = PackedByteArray()

	# Sort keys for deterministic checksum
	var sorted_keys: Array = children.keys()
	sorted_keys.sort()
	
	if sorted_keys.size() == 0:
		combined_data.append(0)
	for key in sorted_keys:
		var child: Dictionary = children[key]
		combined_data.append_array(child["checksum"].to_utf8_buffer())

	ctx.update(combined_data)
	return ctx.finish().hex_encode()


func _get_player_data(player: Player) -> Dictionary:
	"""Extract serializable data from a player"""
	var exp_password: String = Settings.get_setting(Settings.EXP_PASSWORD)
	var player_exp: int = ExperiencePassword.decode(exp_password)

	return {
		"id": player.get_id(),
		"name": player.get_player_name(),
		"experience": player_exp,
		"gold": player.get_gold(),
		"gold_farmed": player.get_gold_farmed(),
		"total_damage": player.get_total_damage(),
		"tomes": player.get_tomes(),
		"team_id": player.get_team().get_id(),
		"lives_percent": player.get_team().get_lives_percent(),
		"level": player.get_team().get_level(),
	}


func _get_tower_data(tower: Tower) -> Dictionary:
	"""Extract serializable data from a tower"""

	return {
		"uid": tower.get_uid(),
		"id": tower.get_id(),
		"position_x": tower.position.x,
		"position_y": tower.position.y,
		"player_id": tower.get_player().get_id(),
		"experience": tower._experience,
		"damage_dealt": tower._damage_dealt_total,
	}


func _get_creep_data(creep: Creep) -> Dictionary:
	"""Extract serializable data from a creep"""

	return {
		"uid": creep.get_uid(),
		"position_x": creep.position.x,
		"position_y": creep.position.y,
		"health": creep.get_health(),
	}


func _get_item_data(item: Item) -> Dictionary:
	"""Extract serializable data from an item"""

	return {
		"uid": item.get_uid(),
		"id": item.get_id(),
		"rarity": item.get_rarity(),
		"carrier_uid": item.get_carrier().get_uid() if item.get_carrier() else 0,
	}


# func _get_projectile_data(projectile) -> Dictionary:
# 	"""Extract serializable data from a projectile"""

# 	return {
# 		"position_x": projectile._position_wc3.x,
# 		"position_y": projectile._position_wc3.y,
# 		"damage_ratio": projectile._damage_ratio,
# 		"crit_ratio": projectile._crit_ratio,
# 		"remaining_lifetime": projectile._lifetime_timer.time_left
# 	}


func _validate_tree_consistency(tree: Dictionary, errors: Array, path: String = ""):
	"""Validate internal consistency of a checksum tree"""

	# Check if checksum matches calculated value
	var calculated_checksum: String = _calculate_combined_checksum(tree.get("children", {}))
	if tree.get("checksum") != calculated_checksum:
		errors.append({
			"path": path,
			"error": "Root checksum mismatch",
			"expected": calculated_checksum,
			"actual": tree.get("checksum"),
		})

	# Validate children recursively
	var children: Dictionary = tree.get("children", {})
	for child_name in children:
		var child_path: String = path + "/" + child_name if path else child_name
		_validate_tree_consistency(children[child_name], errors, child_path)

func _unique_sorted(a: Array) -> Array:
	var b := a.duplicate()
	b.sort()
	var out: Array = []
	var first := true
	var last = null
	for v in b:
		if first or v != last:
			out.append(v)
			last = v
			first = false
	return out

func _compare_tree_nodes(node_a: Dictionary, node_b: Dictionary, path: String, differences: Array):
	"""Compare two tree nodes and record differences"""

	# Compare checksums
	if node_a.get("checksum") != node_b.get("checksum"):
		differences.append({
			"path": path,
			"type": "checksum_mismatch",
			"node_a": node_a.get("checksum"),
			"node_b": node_b.get("checksum"),
		})

	# Compare children if both have them
	var children_a: Dictionary = node_a.get("children", {})
	var children_b: Dictionary = node_b.get("children", {})

	var all_keys: Array = []
	all_keys.append_array(children_a.keys())
	all_keys.append_array(children_b.keys())
	all_keys = _unique_sorted(all_keys)

	for key in all_keys:
		var child_path: String = path + "/" + key if path else key

		if !children_a.has(key):
			differences.append({
				"path": child_path,
				"type": "missing_in_a",
			})
		elif !children_b.has(key):
			differences.append({
				"path": child_path,
				"type": "missing_in_b",
			})
		else:
			_compare_tree_nodes(children_a[key], children_b[key], child_path, differences)


func _get_game_client() -> GameClient:
	if is_instance_valid(_game_client):
		return _game_client
	var game_client: GameClient = get_tree().root.find_child("GameClient", true, false)
	_game_client = game_client
	return _game_client

func _get_current_tick() -> int:
	var game_client: GameClient = _get_game_client()
	if is_instance_valid(game_client):
		return _get_game_client()._current_tick
	return 0
