class_name ChecksumBuilder
extends RefCounted


const HASH_ALGO: HashingContext.HashType = HashingContext.HASH_SHA256


static func build(tick: int) -> Dictionary:
	var children: Array = []
	children.append(_build_players())
	children.append(_build_towers())
	children.append(_build_creeps())

	var filtered_children: Array = []
	for child in children:
		if child == null:
			continue

		var child_children: Array = child.get("children", [])
		var child_data: Variant = child.get("data", {})
		var has_payload: bool = !child_children.is_empty() || !_is_empty_data(child_data)

		if has_payload:
			filtered_children.append(child)

	var root_data: Dictionary = {"tick": tick}
	var root: Dictionary = _make_node("root", root_data, filtered_children)
	root["tick"] = tick

	return root


static func diff(expected: Dictionary, actual: Dictionary, path: Array[String] = []) -> Array[Dictionary]:
	var differences: Array = []

	if expected.get("hash", "") == actual.get("hash", ""):
		return differences

	var current_path: Array[String] = path.duplicate()
	current_path.append(expected.get("name", "unknown"))

	var expected_children: Dictionary = _children_to_map(expected.get("children", []))
	var actual_children: Dictionary = _children_to_map(actual.get("children", []))

	var child_name_set: Array = expected_children.keys()
	for name in actual_children.keys():
		if !child_name_set.has(name):
			child_name_set.append(name)

	child_name_set.sort()

	for child_name in child_name_set:
		var expected_child: Dictionary = expected_children.get(child_name, {})
		var actual_child: Dictionary = actual_children.get(child_name, {})

		var expected_has_child: bool = !expected_child.is_empty()
		var actual_has_child: bool = !actual_child.is_empty()

		if expected_has_child && actual_has_child:
			differences.append_array(diff(expected_child, actual_child, current_path))
		elif expected_has_child && !actual_has_child:
			differences.append({
				"path": current_path + [child_name],
				"expected_hash": expected_child.get("hash", ""),
				"actual_hash": "",
				"expected_data": expected_child.get("data", {}),
				"actual_data": {},
			})
		elif !expected_has_child && actual_has_child:
			differences.append({
				"path": current_path + [child_name],
				"expected_hash": "",
				"actual_hash": actual_child.get("hash", ""),
				"expected_data": {},
				"actual_data": actual_child.get("data", {}),
			})

	if differences.is_empty():
		differences.append({
			"path": current_path,
			"expected_hash": expected.get("hash", ""),
			"actual_hash": actual.get("hash", ""),
			"expected_data": expected.get("data", {}),
			"actual_data": actual.get("data", {}),
		})

	return differences


#########################
###      Private      ###
#########################

static func _build_players() -> Dictionary:
	var player_list: Array[Player] = PlayerManager.get_player_list()
	player_list.sort_custom(func(a: Player, b: Player) -> bool:
		return a.get_id() < b.get_id()
		)

	var tower_count_map: Dictionary = {}
	for tower in Utils.get_tower_list():
		if tower == null:
			continue

		var owner: Player = tower.get_player()
		if owner == null:
			continue

		var owner_id: int = owner.get_id()
		var current_count: int = tower_count_map.get(owner_id, 0)
		tower_count_map[owner_id] = current_count + 1

	var children: Array = []
	for player in player_list:
		if player == null:
			continue

		var owned_towers: int = tower_count_map.get(player.get_id(), 0)
		var data: Dictionary = _collect_player_data(player, owned_towers)
		var label: String = "player:%d" % player.get_id()
		var child_list: Array = []
		child_list.append(_build_player_item_container("stash", player.get_item_stash()))
		child_list.append(_build_player_item_container("horadric", player.get_horadric_stash()))

		var child_nodes: Array = []
		for child in child_list:
			if child == null:
				continue

			child_nodes.append(child)

		var node: Dictionary = _make_node(label, data, child_nodes)
		children.append(node)

	var players_node: Dictionary = _make_node("players", {"count": player_list.size()}, children)

	return players_node


static func _collect_player_data(player: Player, tower_count: int) -> Dictionary:
	var data: Dictionary = {}
	data["id"] = player.get_id()
	data["name"] = player.get_player_name()
	data["gold"] = int(player.get_gold())
	data["gold_farmed"] = int(player.get_gold_farmed())
	data["tomes"] = player.get_tomes()
	data["food"] = player.get_food()
	data["food_cap"] = player.get_food_cap()
	data["score"] = int(player.get_score())
	data["total_damage"] = int(player.get_total_damage())
	data["tower_count"] = tower_count

	var builder: Builder = player.get_builder()
	if builder != null:
		data["builder_id"] = builder.get_id()

	data["element_levels"] = _convert_element_levels(player.get_element_level_map())

	return data


static func _build_player_item_container(label: String, container: ItemContainer) -> Dictionary:
	if container == null:
		return {}

	var children: Array = []
	var highest_index: int = container.get_highest_index()
	for index in range(0, highest_index + 1):
		var item: Item = container.get_item_at_index(index)
		if item == null:
			continue

		var data: Dictionary = _collect_item_data(item)
		data["slot"] = index
		var node_label: String = "%s-item:%d" % [label, item.get_uid()]
		children.append(_make_node(node_label, data, []))

	return _make_node(label, {
		"capacity": container.get_capacity(),
		"uid": container.get_uid(),
	}, children)


static func _collect_item_data(item: Item) -> Dictionary:
	var data: Dictionary = {}
	data["id"] = item.get_id()
	data["uid"] = item.get_uid()
	data["uses_charges"] = item.uses_charges()
	data["charges"] = item.get_charges()
	data["horadric_locked"] = item.get_horadric_lock_is_enabled()
	data["fresh"] = item.get_is_fresh()

	return data


static func _build_towers() -> Dictionary:
	var tower_list: Array[Tower] = Utils.get_tower_list()
	tower_list.sort_custom(func(a: Tower, b: Tower) -> bool:
		return a.get_uid() < b.get_uid()
		)

	var children: Array = []
	for tower in tower_list:
		if tower == null:
			continue

		var data: Dictionary = _collect_tower_data(tower)
		var label: String = "tower:%d" % tower.get_uid()
		children.append(_make_node(label, data, []))

	return _make_node("towers", {"count": tower_list.size()}, children)


static func _collect_tower_data(tower: Tower) -> Dictionary:
	var player: Player = tower.get_player()
	var position: Vector2 = tower.get_position_wc3_2d()

	var item_payload: Array = []
	for item in tower.get_items():
		item_payload.append(_collect_item_data(item))

	var data: Dictionary = {}
	data["uid"] = tower.get_uid()
	data["id"] = tower.get_id()
	data["player_id"] = player.get_id() if player != null else -1
	data["position"] = _vector2_to_array(position)
	data["z"] = tower.get_z()
	data["level"] = tower.get_level()
	data["exp"] = tower.get_exp()
	data["hp"] = tower.get_health()
	data["hp_max"] = tower.get_overall_health()
	data["mana"] = tower.get_mana()
	data["mana_max"] = tower.get_base_mana()
	data["kills"] = tower.get_kills()
	data["total_damage"] = int(tower.get_total_damage())
	data["items"] = item_payload

	return data


static func _build_creeps() -> Dictionary:
	var creep_list: Array[Creep] = Utils.get_creep_list()
	creep_list.sort_custom(func(a: Creep, b: Creep) -> bool:
		return a.get_uid() < b.get_uid()
		)

	var children: Array = []
	for creep in creep_list:
		if creep == null:
			continue

		var data: Dictionary = _collect_creep_data(creep)
		var label: String = "creep:%d" % creep.get_uid()
		children.append(_make_node(label, data, []))

	return _make_node("creeps", {"count": creep_list.size()}, children)


static func _collect_creep_data(creep: Creep) -> Dictionary:
	var position: Vector2 = creep.get_position_wc3_2d()

	var data: Dictionary = {}
	data["uid"] = creep.get_uid()
	data["player_id"] = creep.get_player().get_id()
	data["spawn_level"] = creep.get_spawn_level()
	data["size"] = int(creep.get_size_including_challenge_sizes())
	data["category"] = int(creep.get_category())
	data["armor_type"] = int(creep.get_armor_type())
	data["health"] = creep.get_health()
	data["health_max"] = creep.get_overall_health()
	data["mana"] = creep.get_mana()
	data["position"] = _vector2_to_array(position)
	data["z"] = creep.get_z()
	data["specials"] = creep.get_special_list().duplicate()

	return data


static func _convert_element_levels(level_map: Dictionary) -> Array:
	var result: Array = []
	var keys: Array = level_map.keys()
	keys.sort()

	for element in keys:
		result.append({
			"element": int(element),
			"level": level_map[element],
		})

	return result


static func _children_to_map(children: Array) -> Dictionary:
	var result: Dictionary = {}
	for child in children:
		if child is Dictionary:
			var name: String = child.get("name", "")
			if !name.is_empty():
				result[name] = child

	return result


static func _make_node(name: String, data: Variant, children: Array) -> Dictionary:
	var normalized_children: Array = []
	for child in children:
		if child == null:
			continue

		normalized_children.append(child)

	normalized_children.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return String(a.get("name", "")) < String(b.get("name", ""))
		)

	var node: Dictionary = {
		"name": name,
		"data": data,
		"children": normalized_children,
	}
	node["hash"] = _hash_node(node)

	return node


static func _hash_node(node: Dictionary) -> String:
	var summary: Dictionary = {}
	summary["name"] = node.get("name", "")
	summary["data"] = node.get("data", {})

	var child_summary: Array = []
	for child in node.get("children", []):
		child_summary.append({
			"name": child.get("name", ""),
			"hash": child.get("hash", ""),
		})

	child_summary.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return String(a.get("name", "")) < String(b.get("name", ""))
		)

	summary["children"] = child_summary

	return _hash_variant(summary)


static func _hash_variant(value: Variant) -> String:
	var sanitized: Variant = _sanitize_variant(value)
	var bytes: PackedByteArray = var_to_bytes(sanitized)

	var ctx: HashingContext = HashingContext.new()
	ctx.start(HASH_ALGO)
	ctx.update(bytes)
	var digest: PackedByteArray = ctx.finish()

	return digest.hex_encode()


static func _sanitize_variant(value: Variant) -> Variant:
	match typeof(value):
		TYPE_DICTIONARY:
			var keys: Array = value.keys()
			keys.sort_custom(func(a, b):
				return String(a) < String(b)
				)

			var entries: Array = []
			for key in keys:
				entries.append([String(key), _sanitize_variant(value[key])])

			return ["dict", entries]
		TYPE_ARRAY:
			var sanitized: Array = []
			for item in value:
				sanitized.append(_sanitize_variant(item))

			return ["array", sanitized]
		TYPE_VECTOR2:
			var vec2: Vector2 = value
			return ["vec2", vec2.x, vec2.y]
		TYPE_VECTOR3:
			var vec3: Vector3 = value
			return ["vec3", vec3.x, vec3.y, vec3.z]
		TYPE_VECTOR2I:
			var vec2i: Vector2i = value
			return ["vec2i", vec2i.x, vec2i.y]
		TYPE_VECTOR3I:
			var vec3i: Vector3i = value
			return ["vec3i", vec3i.x, vec3i.y, vec3i.z]
		_:
			return value


static func _vector2_to_array(value: Vector2) -> Array:
	return [value.x, value.y]


static func _is_empty_data(data: Variant) -> bool:
	if typeof(data) == TYPE_DICTIONARY:
		return data.is_empty()

	if typeof(data) == TYPE_ARRAY:
		return data.is_empty()

	return false
