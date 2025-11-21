class_name ActionAutofill


# NOTE: autofill action needs to store the item list because
# it is simpler. An alternative approach would be to pass
# recipe and rarity filter, which couples multiplayer peers
# too much to UI state of player who initiated the autofill
# action.


static func make(autofill_uid_list: Array[int]) -> Action:
	var action: Action = Action.new({
		Action.Field.TYPE: Action.Type.AUTOFILL,
		Action.Field.UID_LIST: autofill_uid_list,
		})

	return action


static func execute(action: Dictionary, player: Player):
	var autofill_uid_list: Array = action[Action.Field.UID_LIST]

	var autofill_list: Array[Item] = []
	for item_uid in autofill_uid_list:
		var item_node: Node = GroupManager.get_by_uid("items", item_uid)
		var item: Item = item_node as Item
		
		# NOTE: Verify checks existence, but we need the object reference for the list
		if item != null:
			autofill_list.append(item)

	if !verify(player, autofill_list):
		return

	var item_stash: ItemContainer = player.get_item_stash()
	var horadric_stash: ItemContainer = player.get_horadric_stash()
	
	# 1. Move items from Towers (or other locations) to Item Stash first
	for item in autofill_list:
		var current_container: Node = item.get_parent()
		
		# If item is in a tower, move it to stash first
		if current_container is ItemContainer and current_container != item_stash and current_container != horadric_stash:
			# We already verified ownership in verify(), so we can just move it
			current_container.remove_item(item)
			item_stash.add_item(item)


# 	Return current horadric cube contents to item stash
#   NOTE: We must iterate over a duplicate because we are modifying the container
	var horadric_items_initial: Array[Item] = horadric_stash.get_item_list()
	for item in horadric_items_initial:
		horadric_stash.remove_item(item)
		item_stash.add_item(item)

#	Move autofill items from item stash to horadric stash
	for item in autofill_list:
		# Item should be in item_stash now (either was there, or moved from tower/cube above)
		if item_stash.has(item):
			item_stash.remove_item(item)
			horadric_stash.add_item(item)
		else:
			print("Error: Item not found in stash during autofill: ", item)


static func verify(player: Player, autofill_list: Array[Item]) -> bool:
	var item_stash: ItemContainer = player.get_item_stash()
	var horadric_stash: ItemContainer = player.get_horadric_stash()
	
	for item in autofill_list:
		if item == null:
			Utils.add_ui_error(player, Utils.tr("MESSAGE_FAILED_TO_AUTOFILL"))
			return false
			
		var current_container: Node = item.get_parent()
		
		# 1. Check if item belongs to the player
		# (This is implicitly checked by checking the container ownership below, 
		# but explicit check is good too)
		if item.get_player() != player:
			Utils.add_ui_error(player, Utils.tr("MESSAGE_DONT_OWN_ITEM"))
			return false

		# 2. Check if container is valid
		if current_container is ItemContainer:
			if current_container == item_stash or current_container == horadric_stash:
				continue
			
			# Check if it is a tower belonging to the player
			var tower: Tower = current_container.get_parent() as Tower
			if tower != null and tower.get_player() == player:
				continue
				
			# If we are here, it's in a container we don't control (e.g. another player's stash/tower)
			Utils.add_ui_error(player, Utils.tr("MESSAGE_DONT_OWN_TOWER")) 
			return false
		else:
			# Item is in a weird state (not in an ItemContainer)
			Utils.add_ui_error(player, Utils.tr("MESSAGE_FAILED_TO_AUTOFILL"))
			return false
			
	return true
