extends Tower


var sir_frost_glacier: BuffType
var cb_stun: BuffType


func get_tier_stats() -> Dictionary:
	return {
		1: {slow_value = 70, extra_damage = 100, damage_and_stun_chance = 0.02, stun_duration = 0.8},
		2: {slow_value = 100, extra_damage = 520, damage_and_stun_chance = 0.03, stun_duration = 0.9},
		3: {slow_value = 130, extra_damage = 1300, damage_and_stun_chance = 0.04, stun_duration = 1.0},
		4: {slow_value = 160, extra_damage = 2150, damage_and_stun_chance = 0.05, stun_duration = 1.1},
	}


func get_ability_description() -> String:
	var slow_value: String = Utils.format_percent(_stats.slow_value * 0.001, 2)
	var slow_add: String = Utils.format_percent(_stats.slow_value / 20.0 * 0.001, 2)
	var extra_damage: String = Utils.format_float(_stats.extra_damage, 2)
	var stun_duration: String = Utils.format_float(_stats.stun_duration, 2)
	var damage_and_stun_chance: String = Utils.format_percent(_stats.damage_and_stun_chance, 2)
	var extra_damage_add: String = Utils.format_float(_stats.extra_damage * 0.02, 2)

	var text: String = ""

	text += "[color=GOLD]Glacial Wrath[/color]\n"
	text += "Attacks of this tower slow the attacked creep by %s for 3 seconds. Each attack has a %s change to deal %s spelldamage and stun the target for %s seconds. The chance to stun the target is increased by %s per attack and resets after a target is stunned.\n" % [slow_value, damage_and_stun_chance, extra_damage, stun_duration, damage_and_stun_chance]
	text += " \n"
	text += "[color=ORANGE]Level Bonus:[/color]\n"
	text += "+%s spelldamage\n" % extra_damage_add
	text += "+%s slow" % slow_add

	return text


func get_ability_description_short() -> String:
	var text: String = ""

	text += "[color=GOLD]Glacial Wrath[/color]\n"
	text += "Attacked creeps are slowed and each attack increases the chance to stun the target.\n"

	return text


func load_triggers(triggers: BuffType):
	triggers.add_event_on_damage(on_damage)


func tower_init():
	var m: Modifier = Modifier.new()
	sir_frost_glacier = BuffType.new("sir_frost_glacier", 0, 0, false, self)
	sir_frost_glacier.set_buff_icon("@@0@@")
	m.add_modification(Modification.Type.MOD_MOVESPEED, 0, -0.001)
	sir_frost_glacier.set_buff_modifier(m)

	sir_frost_glacier.set_buff_tooltip("Slowed\nReduces movement speed.")

	cb_stun = CbStun.new("frosty_rock_stun", 0, 0, false, self)


func on_damage(event: Event):
	var tower: Tower = self

	var creep: Unit = event.get_target()

	sir_frost_glacier.apply_custom_timed(tower, creep, _stats.slow_value * (1 + tower.get_level() / 20.0), 3)
	var current_chance_text: String = "%s Chance" % Utils.format_percent(tower.user_real, 0)
	tower.get_player().display_floating_text_x(current_chance_text, tower, Color8(50, 150, 255, 255), 0.05, 2, 3)

	if tower.calc_chance(tower.user_real) == true && !event.get_target().is_immune():
		CombatLog.log_ability(tower, creep, "Glacial Wrath Bonus")

		cb_stun.apply_only_timed(tower, event.get_target(), 0.8)
		tower.do_spell_damage(creep, _stats.extra_damage * (1 + tower.get_level() * 0.02), tower.calc_spell_crit_no_bonus())
		tower.user_real = _stats.damage_and_stun_chance
	else:
		tower.user_real = tower.user_real + _stats.damage_and_stun_chance


func on_create(_preceding_tower: Tower):
	var tower: Tower = self

	tower.user_real = _stats.damage_and_stun_chance
