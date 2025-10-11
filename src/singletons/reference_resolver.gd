class_name ReferenceResolver extends Node


# Handles resolution of object references between replay sessions.
# Maps old UIDs to new UIDs and resolves complex object references.


var _uid_mapping: Dictionary = {}  # {old_uid -> new_uid}
var _player_mapping: Dictionary = {}  # {old_player_id -> new_player_id}
var _position_mapping: Dictionary = {}  # {old_position -> new_position}


#########################
###       Public      ###
#########################

func resolve_tower_reference(old_uid: int) -> Tower:
	var new_uid = _uid_mapping.get(old_uid, -1)
	if new_uid == -1:
		push_error("Failed to resolve tower reference: " + str(old_uid))
		return null
	
	return GroupManager.get_by_uid("towers", new_uid) as Tower


func resolve_item_reference(old_uid: int) -> Item:
	var new_uid = _uid_mapping.get(old_uid, -1)
	if new_uid == -1:
		push_error("Failed to resolve item reference: " + str(old_uid))
		return null
	
	return GroupManager.get_by_uid("items", new_uid) as Item


func resolve_player_reference(old_player_id: int) -> Player:
	var new_player_id = _player_mapping.get(old_player_id, -1)
	if new_player_id == -1:
		push_error("Failed to resolve player reference: " + str(old_player_id))
		return null
	
	return PlayerManager.get_player(new_player_id)


func resolve_position_reference(old_position: Vector2) -> Vector2:
	var new_position = _position_mapping.get(old_position, Vector2.ZERO)
	if new_position == Vector2.ZERO && old_position != Vector2.ZERO:
		push_error("Failed to resolve position reference: " + str(old_position))
		return Vector2.ZERO
	
	return new_position


func add_uid_mapping(old_uid: int, new_uid: int):
	_uid_mapping[old_uid] = new_uid


func add_player_mapping(old_player_id: int, new_player_id: int):
	_player_mapping[old_player_id] = new_player_id


func add_position_mapping(old_position: Vector2, new_position: Vector2):
	_position_mapping[old_position] = new_position


func clear_mappings():
	_uid_mapping.clear()
	_player_mapping.clear()
	_position_mapping.clear()


func get_tower_identifier(tower: Tower) -> String:
	return str(tower.get_player().get_id()) + "_" + str(tower.get_position_wc3())


func get_creep_identifier(creep: Creep) -> String:
	return str(creep.get_uid()) + "_" + str(creep.get_position_wc3())


func get_item_identifier(item: Item) -> String:
	return str(item.get_player().get_id()) + "_" + str(item.get_uid())


func find_tower_by_identifier(identifier: String) -> Tower:
	var tower_list = Utils.get_tower_list()
	
	for tower in tower_list:
		if get_tower_identifier(tower) == identifier:
			return tower
	
	return null


func find_creep_by_identifier(identifier: String) -> Creep:
	var creep_list = Utils.get_creep_list()
	
	for creep in creep_list:
		if get_creep_identifier(creep) == identifier:
			return creep
	
	return null


func find_item_by_identifier(identifier: String) -> Item:
	var item_list = get_tree().get_nodes_in_group("items")
	
	for item in item_list:
		if get_item_identifier(item) == identifier:
			return item
	
	return null
