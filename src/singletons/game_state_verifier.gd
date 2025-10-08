extends Node
#class_name GameStateVerifier


static var _expected_hash_tree: Dictionary = {}
static var _expected_source: String = ""


static func build_hashed_tree_from_scene(scene: Node) -> Dictionary:
	if scene == null:
		return {}

	var packed_scene := PackedScene.new()
	var pack_err: int = packed_scene.pack(scene)
	if pack_err != OK:
		push_error("Failed to pack scene for hashing: %s" % pack_err)
		return {}

	return _build_hashed_tree_from_state(packed_scene.get_state())


static func compute_scene_digest(scene: Node) -> PackedByteArray:
	var hashed_tree: Dictionary = build_hashed_tree_from_scene(scene)
	if hashed_tree.is_empty():
		return PackedByteArray()

	var root_hash: String = hashed_tree.get("hash", "")
	if root_hash.is_empty():
		return PackedByteArray()

	return Marshalls.base64_to_raw(root_hash)


static func schedule_expected_hash_tree(hash_tree: Dictionary, source: String):
	GameStateVerifier._expected_hash_tree = hash_tree
	GameStateVerifier._expected_source = source


static func has_pending_verification() -> bool:
	return !GameStateVerifier._expected_hash_tree.is_empty()


static func verify_scene(scene: Node):
	if !has_pending_verification():
		return

	var hashed_tree: Dictionary = build_hashed_tree_from_scene(scene)
	var differences: Array = _compare_hash_trees(_expected_hash_tree, hashed_tree, [])
	if differences.is_empty():
		print_verbose("Game state verified successfully for %s" % _expected_source)
	else:
		for diff in differences:
			var path: Array = diff.get("path", [])
			var expected: Variant = diff.get("expected")
			var actual: Variant = diff.get("actual")
			push_error("Game state mismatch at %s expected %s actual %s" % ["/".join(path), expected, actual])

	_expected_hash_tree = {}
	_expected_source = ""


static func _build_hashed_tree_from_state(state: SceneState) -> Dictionary:
	var node_count: int = state.get_node_count()
	var info_list: Array = []

	for node_index in range(node_count):
		var node_dict: Dictionary = {}
		node_dict["name"] = state.get_node_name(node_index)
		node_dict["type"] = state.get_node_type(node_index)
		var properties: Dictionary = {}

		var property_count: int = state.get_node_property_count(node_index)
		for property_index in range(property_count):
			var property_name: String = state.get_node_property_name(node_index, property_index)
			var property_value: Variant = state.get_node_property_value(node_index, property_index)
			properties[property_name] = property_value

		node_dict["properties"] = properties
		node_dict["children"] = []

		var node_path: NodePath = state.get_node_path(node_index)
		var names: Array = _path_to_names(node_path, node_dict["name"])
		info_list.append({
			"names": names,
			"data": node_dict,
		})

	info_list.sort_custom(
		func(a, b) -> bool:
			return a["names"].size() < b["names"].size()
	)

	var key_to_node: Dictionary = {}
	var root: Dictionary = {}

	for info in info_list:
		var names: Array = info["names"]
		var key: String = _join_names(names)
		var data: Dictionary = info["data"]
		key_to_node[key] = data

		if names.size() <= 1:
			root = data
			continue

		var parent_names: Array = names.duplicate()
		parent_names.resize(names.size() - 1)
		var parent_key: String = _join_names(parent_names)
		if key_to_node.has(parent_key):
			var parent_node: Dictionary = key_to_node[parent_key]
			var children: Array = parent_node.get("children", [])
			children.append(data)
			parent_node["children"] = children

	return _attach_hashes(root)


static func _attach_hashes(node: Dictionary) -> Dictionary:
	var children: Array = node.get("children", [])
	var hashed_children: Array = []
	for child in children:
		hashed_children.append(_attach_hashes(child))

	var properties: Dictionary = node.get("properties", {})
	var sorted_keys: Array = properties.keys()
	sorted_keys.sort()
	var buffer := PackedByteArray()
	buffer.append_array(var_to_bytes(node.get("name", "")))
	buffer.append_array(var_to_bytes(node.get("type", "")))
	for key in sorted_keys:
		buffer.append_array(var_to_bytes(key))
		buffer.append_array(var_to_bytes_with_objects(properties[key]))
	for child_dict in hashed_children:
		buffer.append_array(Marshalls.base64_to_raw(child_dict.get("hash", "")))
	
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_MD5)
	ctx.update(buffer)
	var digest: PackedByteArray = ctx.finish()
	var hash_string: String = Marshalls.raw_to_base64(digest)

	return {
		"name": node.get("name", ""),
		"type": node.get("type", ""),
		"properties": properties,
		"children": hashed_children,
		"hash": hash_string,
	}


static func _path_to_names(path: NodePath, node_name: String) -> Array:
	var names: Array = []
	var count: int = path.get_name_count()
	for index in range(count):
		names.append(path.get_name(index))

	if names.is_empty():
		names.append(node_name)

	return names


static func _join_names(names: Array) -> String:
	return "/".join(names)


static func _compare_hash_trees(expected: Dictionary, actual: Dictionary, path: Array) -> Array:
	var differences: Array = []
	var current_path: Array = path.duplicate()
	current_path.append(expected.get("name", ""))

	if expected.get("hash", "") == actual.get("hash", ""):
		return differences

	var expected_children: Array = expected.get("children", [])
	var actual_children: Array = actual.get("children", [])
	var actual_map: Dictionary = {}
	for child in actual_children:
		var key: String = _child_key(child)
		actual_map[key] = child

	for expected_child in expected_children:
		var child_key: String = _child_key(expected_child)
		if actual_map.has(child_key):
			var child_diff: Array = _compare_hash_trees(expected_child, actual_map[child_key], current_path)
			differences.append_array(child_diff)
			actual_map.erase(child_key)
		else:
			differences.append({
				"path": current_path + [expected_child.get("name", "")],
				"expected": expected_child.get("hash", ""),
				"actual": "MISSING",
			})

	for remaining_key in actual_map.keys():
		var remaining_child: Dictionary = actual_map[remaining_key]
		differences.append({
			"path": current_path + [remaining_child.get("name", "")],
			"expected": "MISSING",
			"actual": remaining_child.get("hash", ""),
		})

	if differences.is_empty():
		differences.append({
			"path": current_path,
			"expected": expected.get("hash", ""),
			"actual": actual.get("hash", ""),
		})

	return differences


static func _child_key(node: Dictionary) -> String:
	return "%s:%s" % [node.get("name", ""), node.get("type", "")]
