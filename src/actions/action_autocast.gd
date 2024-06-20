class_name ActionAutocast


static func make(autocast_uid: int, target_uid: int, target_pos: Vector2) -> Action:
	var action: Action = Action.new({
		Action.Field.TYPE: Action.Type.AUTOCAST,
		Action.Field.UID: autocast_uid,
		Action.Field.UID_2: target_uid,
		Action.Field.POSITION: target_pos,
		})

	return action


static func verify(player: Player, autocast: Autocast) -> bool:
	if autocast == null:
		Messages.add_error(player, "Failed to cast")

		return false

	if !autocast.can_cast():
		autocast.add_cast_error_message()

		return false

	var caster: Unit = autocast.get_caster()
	var player_match: bool = caster.get_player() == player
	if !player_match:
		Messages.add_error(player, "You don't own this tower")

		return false

	return true


# NOTE: not doing range check on purpose. Range check is
# performed when action is requested and if target went out
# of range during latency, we still execute the cast.
static func execute(action: Dictionary, player: Player):
	var autocast_uid: int = action[Action.Field.UID]
	var target_uid: int = action[Action.Field.UID_2]
	var target_pos: Vector2 = action[Action.Field.POSITION]
	
	var autocast: Autocast = GroupManager.get_by_uid("autocasts", autocast_uid)

	var verify_ok: bool = ActionAutocast.verify(player, autocast)

	if !verify_ok:
		return

	if autocast.type_is_immediate():
		var target: Unit = null
		autocast.do_cast(target)
	elif autocast.type_is_point():
		autocast.do_cast_at_pos(target_pos)
	else:
		var target: Unit = GroupManager.get_by_uid("units", target_uid)

		if target == null:
			Messages.add_error(player, "Target is not valid.")

			return

		autocast.do_cast(target)
