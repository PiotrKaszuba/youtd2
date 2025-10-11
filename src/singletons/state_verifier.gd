class_name StateVerifier extends Node

# Handles comprehensive game state verification with checksum trees
# Creates hierarchical checksums for detailed state comparison

var _current_verification_tree: Dictionary = {}

# Configuration for checksum frequency and granularity
var _checksum_frequency: int = 30  # Every 30 ticks (1 second at 30 TPS)
var _detailed_checksums_enabled: bool = true  # Enable per-entity detailed checksums
var _last_checksum_tick: int = 0


#########################
###       Public      ###
#########################

func set_checksum_frequency(ticks: int) -> void:
	_checksum_frequency = max(1, ticks)  # Minimum 1 tick


func set_detailed_checksums_enabled(enabled: bool) -> void:
	_detailed_checksums_enabled = enabled


func should_generate_checksum() -> bool:
	var current_tick: int = _get_current_tick()
	return current_tick - _last_checksum_tick >= _checksum_frequency


func generate_checksum_tree() -> Dictionary:
	"""Generate a hierarchical checksum tree of the current game state"""

	# Update last checksum tick
	_last_checksum_tick = _get_current_tick()

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
		root_checksum["children"]["projectiles"] = _generate_projectiles_checksum()

	# Generate root checksum from all children
	root_checksum["checksum"] = _calculate_root_checksum(root_checksum["children"])

	return root_checksum


func verify_current_state() -> Dictionary:
	"""Verify current game state and return any discrepancies"""

	var current_tree: Dictionary = generate_checksum_tree()

	# Compare with expected state if available
	# For now, just validate internal consistency

	var errors: Array = []
	_validate_tree_consistency(current_tree, errors)

	return {
		"valid": errors.is_empty(),
		"errors": errors,
		"tree": current_tree,
	}


func compare_states(state_a: Dictionary, state_b: Dictionary) -> Dictionary:
	"""Compare two state trees and return differences"""

	var differences: Dictionary = {
		"root_different": state_a.get("checksum") != state_b.get("checksum"),
		"differences": [],
	}

	_compare_tree_nodes(state_a, state_b, "", differences["differences"])

	return differences


#########################
###      Private      ###
#########################

func _calculate_root_checksum(children: Dictionary) -> String:
	"""Calculate checksum for the root node based on children"""

	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)

	var combined_data: PackedByteArray = PackedByteArray()

	for child_type in children:
		var child: Dictionary = children[child_type]
		combined_data.append_array(child["checksum"].to_utf8_buffer())

	ctx.update(combined_data)
	return ctx.finish().hex_encode()


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


func _generate_projectiles_checksum() -> Dictionary:
	"""Generate checksum for all projectiles"""

	var projectile_checksums: Dictionary = {}

	var projectile_list: Array = get_tree().get_nodes_in_group("projectiles")
	for projectile in projectile_list:
		var projectile_data: Dictionary = _get_projectile_data(projectile)
		projectile_checksums["projectile_%d" % projectile.get_instance_id()] = {
			"type": "projectile",
			"checksum": _calculate_node_checksum(projectile_data),
			"data": projectile_data,
		}

	var combined_checksum: String = _calculate_combined_checksum(projectile_checksums)

	return {
		"type": "projectiles",
		"checksum": combined_checksum,
		"children": projectile_checksums,
	}


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

	for key in sorted_keys:
		var child: Dictionary = children[key]
		combined_data.append_array(child["checksum"].to_utf8_buffer())

	ctx.update(combined_data)
	return ctx.finish().hex_encode()


func _get_player_data(player: Player) -> Dictionary:
	"""Extract serializable data from a player"""

	return {
		"id": player.get_id(),
		"name": player.get_player_name(),
		"experience": player.get_experience(),
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
		"experience": tower.get_experience(),
		"damage_dealt": tower.get_damage_dealt(),
		"health": tower.get_health(),
		"max_health": tower.get_max_health(),
		"attack_damage": tower.get_attack_damage(),
		"attack_speed": tower.get_attack_speed(),
	}


func _get_creep_data(creep: Creep) -> Dictionary:
	"""Extract serializable data from a creep"""

	return {
		"uid": creep.get_uid(),
		"id": creep.get_id(),
		"position_x": creep.position.x,
		"position_y": creep.position.y,
		"health": creep.get_health(),
		"max_health": creep.get_max_health(),
		"move_speed": creep.get_move_speed(),
		"path_progress": creep.get_path_progress(),
		"wave_id": creep.get_wave_id(),
		"player_id": creep.get_player_id(),
	}


func _get_item_data(item: Item) -> Dictionary:
	"""Extract serializable data from an item"""

	return {
		"uid": item.get_uid(),
		"id": item.get_id(),
		"rarity": item.get_rarity(),
		"carrier_uid": item.get_carrier().get_uid() if item.get_carrier() else 0,
		"container_uid": item.get_container().get_uid() if item.get_container() else 0,
	}


func _get_projectile_data(projectile) -> Dictionary:
	"""Extract serializable data from a projectile"""

	return {
		"position_x": projectile.position.x,
		"position_y": projectile.position.y,
		"direction_x": projectile.direction.x if projectile.direction else 0,
		"direction_y": projectile.direction.y if projectile.direction else 0,
		"damage": projectile.damage if projectile.damage else 0,
		"speed": projectile.speed if projectile.speed else 0,
		"lifetime": projectile.lifetime if projectile.lifetime else 0,
		"remaining_lifetime": projectile.remaining_lifetime if projectile.remaining_lifetime else 0,
	}


func _validate_tree_consistency(tree: Dictionary, errors: Array, path: String = ""):
	"""Validate internal consistency of a checksum tree"""

	# Check if checksum matches calculated value
	var calculated_checksum: String = _calculate_root_checksum(tree.get("children", {}))
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
	all_keys = Utils.unique(all_keys)

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


func _get_current_tick() -> int:
	"""Get current game tick (implementation depends on game architecture)"""

	# For now, use the same implementation as ReplayManager
	return floori(Time.get_ticks_msec() / (1000.0 / 30.0))  # 30 ticks per second
