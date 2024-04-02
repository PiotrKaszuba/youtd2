# Golden Decoration
extends ItemBehavior


var multiboard: MultiboardValues


func get_ability_description() -> String:
	var text: String = ""

	text += "[color=GOLD]Rich[/color]\n"
	text += "Whilst carried by a tower, this item increases the interest rate of the player by [0.4 x carrier's goldcost / 2500]%.\n"

	return text


func load_modifier(modifier: Modifier):
	modifier.add_modification(Modification.Type.MOD_BOUNTY_RECEIVED, 0.10, 0.004)


func item_init():
	multiboard = MultiboardValues.new(1)
	multiboard.set_key(0, "Interest Bonus")


func on_create():
	item.user_real = 0


func on_drop():
	item.get_player().modify_interest_rate(-item.user_real)


func on_pickup():
	var tower: Tower = item.get_carrier()
	item.user_real = 0.004 * (tower.get_gold_cost() / 2500.0)
	item.get_player().modify_interest_rate(item.user_real)


func on_tower_details() -> MultiboardValues:
	multiboard.set_value(0, Utils.format_percent(item.user_real, 3))
	return multiboard
