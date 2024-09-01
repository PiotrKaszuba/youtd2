class_name ActionSelectBuilder


static func make(builder_id_arg: int) -> Action:
	var action: Action = Action.new({
		Action.Field.TYPE: Action.Type.SELECT_BUILDER,
		Action.Field.BUILDER_ID: builder_id_arg,
		})

	return action


static func execute(action: Dictionary, player: Player):
	var builder_id: int = action[Action.Field.BUILDER_ID]

	var verify_ok: bool = ActionSelectBuilder.verify(player)
	if !verify_ok:
		return
	
	player.set_builder(builder_id)

	var player_name: String = player.get_player_name_with_color()
	var builder: Builder = player.get_builder()
	var builder_name: String = builder.get_display_name()
	var message: String = "%s selected builder: %s" % [player_name, builder_name]
	Messages.add_normal(null, message)
	
	var is_local_player: bool = player == PlayerManager.get_local_player()
	if is_local_player:
		EventBus.player_selected_builder.emit()


static func verify(player: Player) -> bool:
	var builder_already_selected: bool = player.get_builder() != null

	if !builder_already_selected:
		Utils.add_ui_error(player, "You already selected a builder")

		return false

	return true
