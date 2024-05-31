class_name ChatCommands extends Node

# Processes chat commands. All chat messages which start
# with "/" are treated as commands.


const GAMESPEED_MIN: int = 1
const GAMESPEED_MAX: int = 30


const HELP: String = "/help"
const READY: String = "/ready"
const AUTOSPAWN: String = "/autospawn"
const AUTOOIL: Array[String] = ["/autooil", "/ao"]
const GAMESPEED: String = "/gamespeed"

const CREATE_ITEM: String = "/createitem"
const PAUSE: String = "/pause"
const UNPAUSE: String = "/unpause"
const ADD_EXP: String = "/add-exp"
const ADD_TEST_OILS: String = "/add-test-oils"
const SPAWN_CHALLENGE: String = "/spawn-challenge"
const SETUP_TEST_TOWER: String = "/setup-test-tower"

const NOT_ALLOWED_IN_MULTIPLAYER_LIST: Array[String] = [
	AUTOSPAWN,
	GAMESPEED,
]

const DEV_COMMAND_LIST: Array[String] = [
	CREATE_ITEM,
	PAUSE,
	UNPAUSE,
	ADD_EXP,
	ADD_TEST_OILS,
	SPAWN_CHALLENGE,
	SETUP_TEST_TOWER,
]

@export var _team_container: TeamContainer


#########################
###       Public      ###
#########################

func process_command(player: Player, command: String):
	var command_split: Array = command.split(" ")
	var command_main: String = command_split[0]
	var command_args: Array = command_split.slice(1)

	var player_mode: PlayerMode.enm = Globals.get_player_mode()
	var is_multiplayer: bool = player_mode == PlayerMode.enm.COOP
	var command_not_allowed_in_multiplayer: bool = NOT_ALLOWED_IN_MULTIPLAYER_LIST.has(command_main)
	if is_multiplayer && command_not_allowed_in_multiplayer:
		_add_error(player, "This command is not allowed in multiplayer.")

		return

	var command_is_dev: bool = DEV_COMMAND_LIST.has(command_main)
	var enable_dev_commands: bool = Config.enable_dev_commands()
	if command_is_dev && !enable_dev_commands:
		_add_error(player, "This command is only available in dev mode.")
		
		return

	if ChatCommands.AUTOOIL.has(command_main):
		_command_autooil(player, command_args)

		return

	match command_main:
		ChatCommands.HELP: _command_help(player)
		ChatCommands.READY: _command_ready(player)
		ChatCommands.GAMESPEED: _command_gamespeed(player, command_args)
		ChatCommands.PAUSE: _command_pause(player)
		ChatCommands.UNPAUSE: _command_unpause(player)
		ChatCommands.CREATE_ITEM: _command_create_item(player, command_args)
		ChatCommands.AUTOSPAWN: _command_autospawn(player, command_args)
		ChatCommands.ADD_EXP: _command_add_exp(player, command_args)
		ChatCommands.ADD_TEST_OILS: _command_add_test_oils(player, command_args)
		ChatCommands.SPAWN_CHALLENGE: _command_spawn_challenge(player, command_args)
		ChatCommands.SETUP_TEST_TOWER: _command_setup_test_tower(player, command_args)
		_: _add_error(player, "Unknown command: %s" % command_main)


#########################
###      Private      ###
#########################

func _command_help(player: Player):
	_add_status(player, "You can read about chat commands in the [color=GOLD]Advanced[/color] tab of the [color=GOLD]Hints[/color] menu.")


func _command_ready(player: Player):
	if !player.is_ready():
		player.vote_ready()


func _command_gamespeed(player: Player, args: Array):
	if args.size() != 1:
		_add_error(player, "Invalid command args.")

		return

	var value: int = args[0].to_int()

	if GAMESPEED_MIN > value || value > GAMESPEED_MAX:
		_add_error(player, "Gamespeed value must be within [%s,%s] range." % [GAMESPEED_MIN, GAMESPEED_MAX])

		return

	Globals.set_update_ticks_per_physics_tick(value)

	_add_status(player, "Set gamespeed to %d." % value)


func _command_pause(_player: Player):
	var team_list: Array[Team] = _team_container.get_team_list()
	for team in team_list:
		team.set_waves_paused(true)

	_add_status(null, "Paused the waves. Unpause by typing /unpause.")


func _command_unpause(_player: Player):
	var team_list: Array[Team] = _team_container.get_team_list()
	for team in team_list:
		team.set_waves_paused(false)

	_add_status(null, "Unpaused the waves.")


func _command_create_item(player: Player, args: Array):
	if args.size() != 1:
		_add_error(player, "Invalid command args.")

		return

	var item_id: int = args[0].to_int()
	var item: Item = Item.create(player, item_id, Vector3(0, 0, 0))
	item.fly_to_stash(0.0)

	_add_status(player, "Created item %d" % item_id)


# TODO: in multiplayer, it should not be possible for one
# player to change autospawn for whole team. Both players
# need to input same value to agree?
func _command_autospawn(player: Player, args: Array):
	if args.size() != 1:
		_add_error(player, "Invalid command args.")

		return

	var team: Team = player.get_team()

	var option: String = args[0]
	var disable_autospawn: bool = option == "off"

	if disable_autospawn:
		team.set_autospawn_time(-1)
		_add_status(player, "Disabled autospawn.")

		return

	var autospawn_time: int = option.to_int()

	if 1.0 > autospawn_time || autospawn_time > 100:
		_add_error(player, "Invalid time argument.")

		return

	team.set_autospawn_time(autospawn_time)

	_add_status(player, "Set autospawn time to [color=GOLD]%d[/color]." % roundi(autospawn_time))


func _command_autooil(player: Player, args: Array):
	var unit: Unit = player.get_selected_unit()

	var selected_non_tower: bool = unit != null && !unit is Tower
	if selected_non_tower:
		_add_error(player, "Cannot autooil while selecting non-tower units.")

		return

	var tower: Tower = unit as Tower

	var option: String
	if !args.is_empty():
		option = args[0]
	else:
		option = ""
	
	var clear_all: bool = option == "clear" && tower == null
	if clear_all:
		player.clear_all_autooil()
		_add_status(player, "Cleared all autooils.")
		
		return
	
	var clear_tower: bool = option == "clear" && tower != null
	if clear_tower:
		player.clear_autooil_for_tower(tower)
		var tower_name: String = tower.get_display_name()
		_add_status(player, "Cleared autooils for %s." % tower_name)
		
		return
	
	var show_status: bool = option == "show"
	if show_status:
		var status_text: String = player.get_autooil_status()
		_add_status(player, "Autooil status:")
		Messages.add_normal(player, status_text)
		
		return
	
	var list_types: bool = option == "list"
	if list_types:
		var oil_type_list: Array = AutoOil.get_oil_type_list()
		var text: String = ", ".join(oil_type_list)
		_add_status(player, "Available oils for autooil:")
		_add_status(player, text)
		
		return
	
	if tower == null:
		_add_error(player, "You must select a tower to execute this mode of autooil command.")
		
		return
	
	var oil_type: String = option
	var oil_type_is_valid: bool = AutoOil.get_oil_type_is_valid(oil_type)
	
	if !oil_type_is_valid:
		_add_error(player, "Invalid oil type: \"%s\"." % oil_type)

		return
	
	player.set_autooil_for_tower(oil_type, tower)
	var tower_name: String = tower.get_display_name()
	var full_oil_type: String = AutoOil.convert_short_type_to_full(oil_type)
	_add_status(player, "Set autooil for tower [color=GOLD]%s[/color] to [color=GOLD]%s[/color] oils." % [tower_name, full_oil_type])


func _command_add_exp(player: Player, args: Array):
	if args.size() != 1:
		_add_error(player, "Invalid command args.")

		return

	var selected_tower: Unit = player.get_selected_unit()

	if selected_tower == null:
		_add_error(player, "You must selected a tower before executing this command.")

		return

	var exp_amount: int = args[0].to_int()
	selected_tower.add_exp(exp_amount)

	_add_status(player, "Added %d exp to selected tower." % exp_amount)


func _command_add_test_oils(player: Player, _args: Array):
	var selected_tower: Unit = player.get_selected_unit()

	if selected_tower == null:
		_add_error(player, "You must selected a tower before executing this command.")

		return

	_add_test_oils(player, selected_tower)
	_add_status(player, "Added test oils to selected tower.")


func _command_spawn_challenge(player: Player, args: Array):
	if args.size() != 1:
		_add_error(player, "Invalid command args.")

		return

	var creep_level: int = args[0].to_int()
	var armor_type: ArmorType.enm = ArmorType.enm.ZOD
	var difficulty: Difficulty.enm = Globals.get_difficulty()
	var creep_health: float = Wave._calculate_base_hp(creep_level, difficulty, armor_type)
	var creep_armor: float = Wave._calculate_base_armor(creep_level, difficulty)
	var creep_path: Path2D = Utils.find_creep_path(player, false)

	var creep_scene: PackedScene = Preloads.creep_scenes["ChallengeBoss"]
	var creep: Creep = creep_scene.instantiate()
	creep.set_path(creep_path)
	creep.set_player(player)
	creep.set_creep_size(CreepSize.enm.CHALLENGE_BOSS)
	creep.set_armor_type(armor_type)
	creep.set_category(CreepCategory.enm.CHALLENGE)
	creep.set_base_health(creep_health)
	creep.set_health(creep_health)
	creep.set_base_armor(creep_armor)
	creep.set_spawn_level(creep_level)
	Utils.add_object_to_world(creep)

	_add_status(player, "Spawned level %d challenge." % creep_level)


func _command_setup_test_tower(player: Player, _args: Array):
	var selected_tower: Unit = player.get_selected_unit()

	if selected_tower == null:
		_add_error(player, "You must selected a tower before executing this command.")

		return

	selected_tower.add_exp(1000)
	_add_test_oils(player, selected_tower)
	_add_status(player, "Test tower is ready")


# NOTE: oil counts are based on average oil counts obtained
# by wave 200
func _add_test_oils(player: Player, tower: Tower):
	const test_oil_map: Dictionary = {
		1001: 20, # sharpness (attack damage)
		1002: 10, # arcane sharpness (attack damage)
		1003: 3,  # divine sharpness (attack damage)

		1004: 20, # magic (mana pool and regen)
		1005: 10, # magic (mana pool and regen)
		1006: 3, # magic (mana pool and regen)

		1007: 20, # accuracy (attack crit)
		1008: 10, # accuracy (attack crit)
		1009: 3, # accuracy (attack crit)

		1010: 20, # swiftness (attack speed)
		1011: 10, # swiftness (attack speed)
		1012: 3, # swiftness (attack speed)

		1013: 20, # sorcery (spell damage and spell crit)
		1014: 10, # sorcery (spell damage and spell crit)
		1015: 3, # sorcery (spell damage and spell crit)
	}

	for oil_id in test_oil_map.keys():
		var oil_count: int = test_oil_map[oil_id]

		for i in range(0, oil_count):
			var oil_item: Item = Item.create(player, oil_id, Vector3.ZERO)
			oil_item.pickup(tower)


func _add_status(player: Player, text: String):
	Messages.add_normal(player, "[color=CYAN]%s[/color]" % text)


func _add_error(player: Player, text: String):
	Messages.add_normal(player, "[color=RED]%s[/color]" % text)
