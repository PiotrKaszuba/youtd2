extends Node

# Provides lookup for nodes via uid. Note that uid ranges
# can be different for each group.


var _group_map: Dictionary = {}


#########################
###       Public      ###
#########################

func add(group_name: String, node: Node, uid: int):
	node.add_to_group(group_name)

	if !_group_map.has(group_name):
		_group_map[group_name] = {}

	_group_map[group_name][uid] = node


func get_by_uid(group_name: String, uid: int) -> Node:
	if !_group_map.has(group_name):
		return null

	if !_group_map[group_name].has(uid):
		return null

	var is_valid: bool = is_instance_valid(_group_map[group_name][uid])

	if !is_valid:
		return

	var node: Node = _group_map[group_name][uid]

	if node.is_queued_for_deletion():
		return null

	return node


func reset():
	_group_map = {}


func get_serialized_state(scene: Node) -> Dictionary:
	var state: Dictionary = {}
	for group_name in _group_map.keys():
		var uid_map: Dictionary = _group_map[group_name]
		var serialized_group: Dictionary = {}
		for uid in uid_map.keys():
			var node: Node = uid_map[uid]
			if node == null:
				continue
			if !is_instance_valid(node):
				continue
			var path: String = ""
			if scene != null && scene.is_inside_tree() && node.is_inside_tree():
				if scene.is_ancestor_of(node):
					var relative_path: NodePath = scene.get_path_to(node)
					path = String(relative_path)
			serialized_group[uid] = path
		state[group_name] = serialized_group
	return state


func apply_serialized_state(scene: Node, state: Dictionary):
	_group_map = {}
	for group_name in state.keys():
		var serialized_group: Dictionary = state[group_name]
		var resolved: Dictionary = {}
		for uid in serialized_group.keys():
			var node_path: String = serialized_group[uid]
			var node: Node = null
			if scene != null && !node_path.is_empty():
				node = scene.get_node_or_null(NodePath(node_path))
			if node == null:
				continue
			node.add_to_group(group_name)
			resolved[uid] = node
		if !resolved.is_empty():
			_group_map[group_name] = resolved
