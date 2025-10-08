extends RefCounted
class_name AutoloadStateSerializer

static func capture_state(scene: Node) -> Dictionary:
	var state: Dictionary = {}
	state["Globals"] = Globals.get_serialized_state(scene)
	state["PlayerManager"] = PlayerManager.get_serialized_state()
	state["GroupManager"] = GroupManager.get_serialized_state(scene)
	return state

static func restore_state(scene: Node, state: Dictionary):
	if state.is_empty():
		return
	var globals_state: Dictionary = state.get("Globals", {})
	if !globals_state.is_empty():
		Globals.apply_serialized_state(scene, globals_state)
	var player_state: Dictionary = state.get("PlayerManager", {})
	if !player_state.is_empty():
		PlayerManager.apply_serialized_state(player_state)
	var group_state: Dictionary = state.get("GroupManager", {})
	if !group_state.is_empty():
		GroupManager.apply_serialized_state(scene, group_state)
