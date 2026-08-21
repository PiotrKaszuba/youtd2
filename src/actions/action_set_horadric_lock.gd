class_name ActionSetHoradricLock


static func make(item_uid: int, enabled: bool) -> Action:
	return Action.new({
		Action.Field.TYPE: Action.Type.SET_HORADRIC_LOCK,
		Action.Field.UID: item_uid,
		Action.Field.ENABLED: enabled,
	})


static func execute(action: Dictionary, player: Player):
	var item_uid: int = action[Action.Field.UID]
	var item: Item = GroupManager.get_by_uid("items", item_uid) as Item
	if !verify(player, item):
		return

	var enabled: bool = action[Action.Field.ENABLED]
	item.set_horadric_lock(enabled)


static func verify(player: Player, item: Item) -> bool:
	if item == null:
		return false

	if item.get_player() != player:
		Utils.add_ui_error(player, Utils.tr("MESSAGE_DONT_OWN_ITEM"))
		return false

	var item_container: ItemContainer = item.get_parent() as ItemContainer
	if item_container == null || item_container.get_player() != player || !item_container.has(item):
		return false

	return true
