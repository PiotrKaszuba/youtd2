# Sword of Reckoning
extends ItemBehavior


var drol_sword_reck_bt: BuffType


func get_ability_description() -> String:
	var text: String = ""

	text += "[color=GOLD]Holy Wrath - Aura[/color]\n"
	text += "Grants 12% bonus damage against undead to all towers within 200 range.\n"
	text += " \n"
	text += "[color=ORANGE]Level Bonus:[/color]\n"
	text += "+0.24% damage\n"

	return text


func item_init():
	drol_sword_reck_bt = BuffType.create_aura_effect_type("drol_sword_reck_bt", true, self)
	drol_sword_reck_bt.set_buff_icon("cup_with_wings.tres")
	drol_sword_reck_bt.set_buff_tooltip("Holy Wrath\nIncreases damage dealt to Undead.")
	drol_sword_reck_bt.set_stacking_group("drol_sword_reck_bt")
	var mod: Modifier = Modifier.new()
	mod.add_modification(Modification.Type.MOD_DMG_TO_UNDEAD, 0.12, 0.0024)
	drol_sword_reck_bt.set_buff_modifier(mod)

	var aura: AuraType = AuraType.new()
	aura.aura_range = 200
	aura.target_type = TargetType.new(TargetType.TOWERS)
	aura.target_self = true
	aura.level = 0
	aura.level_add = 1
	aura.power = 0
	aura.power_add = 1
	aura.aura_effect = drol_sword_reck_bt
	item.add_aura(aura)
