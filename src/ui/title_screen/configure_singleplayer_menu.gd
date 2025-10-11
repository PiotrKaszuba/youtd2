class_name ConfigureSinglePlayerMenu extends PanelContainer


signal cancel_pressed()
signal start_button_pressed()
signal load_replay_pressed(replay_file_path: String)


@export var _match_config_panel: MatchConfigPanel
@export var _new_game_button: Button
@export var _load_replay_button: Button
@export var _replay_file_selector: VBoxContainer


#########################
###     Built-in      ###
#########################

func _ready():
	# Start in new game mode
	_new_game_button.button_pressed = true
	_update_mode_display()

	var cached_difficulty_string: String = Settings.get_setting(Settings.CACHED_GAME_DIFFICULTY)
	var cached_difficulty: Difficulty.enm = Difficulty.from_string(cached_difficulty_string)

	var cached_game_mode_string: String = Settings.get_setting(Settings.CACHED_GAME_MODE)
	var cached_game_mode: GameMode.enm = GameMode.from_string(cached_game_mode_string)

	var cached_game_length: int = Settings.get_setting(Settings.CACHED_GAME_LENGTH)

	_match_config_panel.set_difficulty(cached_difficulty)
	_match_config_panel.set_game_mode(cached_game_mode)
	_match_config_panel.set_game_length(cached_game_length)

	_match_config_panel.hide_team_mode_selector()


#########################
###       Public      ###
#########################

func get_difficulty() -> Difficulty.enm:
	return _match_config_panel.get_difficulty()


func get_game_length() -> int:
	return _match_config_panel.get_game_length()


func get_game_mode() -> GameMode.enm:
	return _match_config_panel.get_game_mode()


func is_new_game_mode() -> bool:
	return _new_game_button.button_pressed


func get_selected_replay_id() -> String:
	if _replay_file_selector and _replay_file_selector.visible:
		return _replay_file_selector.get_selected_replay_id()
	return ""


#########################
###      Private      ###
#########################

func _update_mode_display():
	var is_new_game: bool = _new_game_button.button_pressed

	_match_config_panel.visible = is_new_game
	_replay_file_selector.visible = !is_new_game

	# Disable/enable match config panel based on mode
	if _match_config_panel:
		_match_config_panel.set_disabled(!is_new_game)


#########################
###     Callbacks     ###
#########################

func _on_new_game_button_toggled(toggled_on: bool):
	if toggled_on:
		_update_mode_display()


func _on_load_replay_button_toggled(toggled_on: bool):
	if toggled_on:
		_update_mode_display()


func _on_start_button_pressed():
	if is_new_game_mode():
		start_button_pressed.emit()
	else:
		var replay_id: String = get_selected_replay_id()
		if !replay_id.is_empty():
			load_replay_pressed.emit(replay_id)


func _on_cancel_button_pressed():
	cancel_pressed.emit()


func _on_new_game_button_toggled(toggled_on: bool):
	if toggled_on:
		_update_mode_display()


func _on_load_replay_button_toggled(toggled_on: bool):
	if toggled_on:
		_update_mode_display()


func _on_replay_file_selector_replay_selected(file_path: String):
	# Enable start button when replay is selected
	pass
