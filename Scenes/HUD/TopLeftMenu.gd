class_name TopLeftMenu extends PanelContainer


@export var _wave_status: WaveStatus
@export var _game_stats: GameStats


func set_gold(gold: float):
	_game_stats.set_gold(gold)


func set_pregame_settings(wave_count: int, game_mode: GameMode.enm, difficulty: Difficulty.enm, builder_id: int):
	_game_stats.set_pregame_settings(wave_count, game_mode, difficulty, builder_id)


func show_game_start_time():
	_wave_status.show_game_start_time()

func hide_game_start_time():
	_wave_status.hide_game_start_time()


func show_next_wave_button():
	_wave_status.show_next_wave_button()
	
	
func show_next_wave_time(time: float):
	_wave_status.show_next_wave_time(time)


func hide_next_wave_time():
	_wave_status.hide_next_wave_time()


func show_wave_details(wave_list: Array[Wave]):
	_wave_status.show_wave_details(wave_list)


func disable_next_wave_button():
	_wave_status.disable_next_wave_button()


func set_level(level: int):
	_wave_status.set_level(level)
	_game_stats.set_level(level)


func set_lives(lives: float):
	_wave_status.set_lives(lives)
	_game_stats.set_lives(lives)


func set_total_damage(total_damage: float):
	_wave_status.set_total_damage(total_damage)
	_game_stats.set_total_damage(total_damage)


func set_gold_farmed(gold_farmed: float):
	_wave_status.set_gold_farmed(gold_farmed)


func set_game_time(time: float):
	_wave_status.set_game_time(time)


func set_score(score: int):
	_wave_status.set_score(score)
