class_name ChecksumBuilder


# Generates hierarchical checksums of game state for replay verification.
# Creates a tree structure with checksums at each level for detailed comparison.


#########################
###       Public      ###
#########################

# Generate complete hierarchical checksum tree
static func build_checksum_tree(tick: int) -> Dictionary:
	var root: Dictionary = {
		"tick": tick,
		"checksum": "",
		"children": {}
	}
	
	var player_list: Array[Player] = PlayerManager.get_player_list()
	
	# Build per-player checksums
	for player in player_list:
		var player_id: int = player.get_id()
		var player_key: String = "player_%d" % player_id
		root["children"][player_key] = _build_player_checksum(player)
	
	# Build global creeps checksum
	root["children"]["creeps"] = _build_creeps_checksum()
	
	# Calculate root checksum from children
	root["checksum"] = _calculate_node_checksum(root)
	
	return root


#########################
###      Private      ###
#########################

static func _build_player_checksum(player: Player) -> Dictionary:
	var player_id: int = player.get_id()
	var player_node: Dictionary = {
		"path": "player_%d" % player_id,
		"checksum": "",
		"data": {
			"gold": floori(player.get_gold()),
			"tomes": player.get_tomes(),
			"total_damage": floori(player.get_total_damage()),
			"gold_farmed": floori(player.get_gold_farmed()),
			"food": player.get_food(),
			"food_cap": player.get_food_cap(),
		},
		"children": {}
	}
	
	# Add team data
	var team: Team = player.get_team()
	player_node["data"]["lives"] = floori(team.get_lives_percent())
	player_node["data"]["level"] = team.get_level()
	
	# Build towers checksum
	player_node["children"]["towers"] = _build_towers_checksum(player)
	
	# Build items checksum
	player_node["children"]["items"] = _build_items_checksum(player)
	
	# Calculate player checksum from data and children
	player_node["checksum"] = _calculate_node_checksum(player_node)
	
	return player_node


static func _build_towers_checksum(player: Player) -> Dictionary:
	var player_id: int = player.get_id()
	var towers_node: Dictionary = {
		"path": "player_%d/towers" % player_id,
		"checksum": "",
		"children": {}
	}
	
	var tower_list: Array[Tower] = Utils.get_tower_list()
	var player_towers: Array[Tower] = []
	
	for tower in tower_list:
		if tower.get_player() == player:
			player_towers.append(tower)
	
	# Sort towers by position for determinism
	player_towers.sort_custom(func(a: Tower, b: Tower) -> bool:
		var pos_a: Vector2 = a.get_position()
		var pos_b: Vector2 = b.get_position()
		if pos_a.x != pos_b.x:
			return pos_a.x < pos_b.x
		return pos_a.y < pos_b.y
	)
	
	for tower in player_towers:
		var tower_id: int = tower.get_id()
		var pos: Vector2 = tower.get_position()
		var tower_key: String = "tower_%d_%.0fx%.0f" % [tower_id, pos.x, pos.y]
		
		towers_node["children"][tower_key] = _build_tower_checksum(tower, tower_key)
	
	towers_node["checksum"] = _calculate_node_checksum(towers_node)
	
	return towers_node


static func _build_tower_checksum(tower: Tower, path: String) -> Dictionary:
	var tower_node: Dictionary = {
		"path": path,
		"checksum": "",
		"data": {
			"id": tower.get_id(),
			"uid": tower.get_uid(),
			"level": tower.get_level(),
			"exp": floori(tower.get_exp()),
			"health": floori(tower.get_health()),
			"mana": floori(tower.get_mana()),
			"kill_count": tower.get_kill_count(),
			"damage_dealt": floori(tower.get_damage_dealt_total()),
		}
	}
	
	tower_node["checksum"] = _calculate_node_checksum(tower_node)
	
	return tower_node


static func _build_items_checksum(player: Player) -> Dictionary:
	var player_id: int = player.get_id()
	var items_node: Dictionary = {
		"path": "player_%d/items" % player_id,
		"checksum": "",
		"children": {}
	}
	
	var item_stash: ItemContainer = player.get_item_stash()
	var item_list: Array[Item] = item_stash.get_item_list()
	
	# Sort items by UID for determinism
	item_list.sort_custom(func(a: Item, b: Item) -> bool:
		return a.get_uid() < b.get_uid()
	)
	
	for item in item_list:
		var item_key: String = "item_%d" % item.get_uid()
		items_node["children"][item_key] = _build_item_checksum(item, item_key)
	
	items_node["checksum"] = _calculate_node_checksum(items_node)
	
	return items_node


static func _build_item_checksum(item: Item, path: String) -> Dictionary:
	var item_node: Dictionary = {
		"path": path,
		"checksum": "",
		"data": {
			"id": item.get_id(),
			"uid": item.get_uid(),
			"charges": item.get_charges(),
		}
	}
	
	item_node["checksum"] = _calculate_node_checksum(item_node)
	
	return item_node


static func _build_creeps_checksum() -> Dictionary:
	var creeps_node: Dictionary = {
		"path": "creeps",
		"checksum": "",
		"children": {}
	}
	
	var creep_list: Array[Creep] = Utils.get_creep_list()
	
	# Sort creeps by UID for determinism
	creep_list.sort_custom(func(a: Creep, b: Creep) -> bool:
		return a.get_uid() < b.get_uid()
	)
	
	for creep in creep_list:
		var creep_key: String = "creep_%d" % creep.get_uid()
		creeps_node["children"][creep_key] = _build_creep_checksum(creep, creep_key)
	
	creeps_node["checksum"] = _calculate_node_checksum(creeps_node)
	
	return creeps_node


static func _build_creep_checksum(creep: Creep, path: String) -> Dictionary:
	var pos: Vector2 = creep.get_position()
	var creep_node: Dictionary = {
		"path": path,
		"checksum": "",
		"data": {
			"uid": creep.get_uid(),
			"health": floori(creep.get_health()),
			"pos_x": floori(pos.x),
			"pos_y": floori(pos.y),
		}
	}
	
	creep_node["checksum"] = _calculate_node_checksum(creep_node)
	
	return creep_node


# Calculate checksum for a node based on its data and children
static func _calculate_node_checksum(node: Dictionary) -> String:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_MD5)
	
	# Hash data if present
	if node.has("data"):
		var data_string: String = JSON.stringify(node["data"])
		ctx.update(data_string.to_utf8_buffer())
	
	# Hash children checksums if present
	if node.has("children"):
		var children: Dictionary = node["children"]
		var keys: Array = children.keys()
		keys.sort()  # Sort for determinism
		
		for key in keys:
			var child: Dictionary = children[key]
			if child.has("checksum"):
				ctx.update(child["checksum"].to_utf8_buffer())
	
	var hash: PackedByteArray = ctx.finish()
	return hash.hex_encode()

