extends Node


@onready var map_node: Node2D = $Map
@onready var _pregame_hud: Control = $UI/PregameHUD
@onready var _wave_spawner: WaveSpawner = $Map/WaveSpawner

var portal_lives: float = 100.0


@export var creeps_game_over_count: int = 10
@export var ignore_game_over: bool = true


func _ready():
	print_verbose("GameScene has loaded.")

	var show_pregame_settings_menu: bool = Config.show_pregame_settings_menu()
	
	if show_pregame_settings_menu:
		_pregame_hud.show()
	else:
#		Skip pregame settings menu and load default values
		var default_wave_count: int = Config.default_wave_count()
		var default_distribution: Distribution.enm = Config.default_distribution()
		var default_difficulty: Difficulty.enm = Config.default_difficulty()

		_on_pregame_hud_finished(default_wave_count, default_distribution, default_difficulty)


func _on_HUD_start_wave(wave_index):
	$Map/CreepSpawner.start(wave_index)


func _on_HUD_stop_wave():
	$Map/CreepSpawner.stop()


func _on_CreepExit_body_entered(body):
	if body is Creep:
		var damage = body.reach_portal()
		portal_lives -= damage


func _on_WaveSpawner_wave_ended(_wave_index):
	GoldControl.add_income()
	KnowledgeTomesManager.add_knowledge_tomes()


# TODO: use distribution setting
func _on_pregame_hud_finished(wave_count: int, _distribution: Distribution.enm, difficulty: Difficulty.enm):
	_pregame_hud.hide()

	var difficulty_string: String = Difficulty.convert_to_string(difficulty).to_upper()


	Messages.add_normal("Welcome to youtd 2!")
	Messages.add_normal("Game settings: %d waves, %s difficulty" % [wave_count, difficulty_string])
	Messages.add_normal("Move the camera with arrow keys or WASD.")
	Messages.add_normal("To build towers, click on the tower button in the bottom right corner.")
	Messages.add_normal("Select one of the elements and pick a tower.")
	Messages.add_normal("Move the mouse cursor to a spot where you want to build the tower.")
	Messages.add_normal("When there's a valid build position, the tower under the cursor will turn green.")

	_wave_spawner.generate_waves(wave_count, difficulty)


