class_name ConfigureSinglePlayerMenu extends PanelContainer


signal cancel_pressed()
signal start_button_pressed()


@export var _match_config_panel: MatchConfigPanel
@export var _replay_summary_label: Label
@export var _replay_select_button: Button
@export var _replay_clear_button: Button
@export var _replay_file_dialog: FileDialog


#########################
###     Built-in      ###
#########################

func _ready():
	var cached_difficulty_string: String = Settings.get_setting(Settings.CACHED_GAME_DIFFICULTY)
	var cached_difficulty: Difficulty.enm = Difficulty.from_string(cached_difficulty_string)
	
	var cached_game_mode_string: String = Settings.get_setting(Settings.CACHED_GAME_MODE)
	var cached_game_mode: GameMode.enm = GameMode.from_string(cached_game_mode_string)
	
	var cached_game_length: int = Settings.get_setting(Settings.CACHED_GAME_LENGTH)

	_match_config_panel.set_difficulty(cached_difficulty)
	_match_config_panel.set_game_mode(cached_game_mode)
	_match_config_panel.set_game_length(cached_game_length)
	
	_match_config_panel.hide_team_mode_selector()
	_replay_file_dialog.current_dir = "user://replays"
	_refresh_replay_selection_ui()


#########################
###       Public      ###
#########################

func get_difficulty() -> Difficulty.enm:
	return _match_config_panel.get_difficulty()


func get_game_length() -> int:
	return _match_config_panel.get_game_length()


func get_game_mode() -> GameMode.enm:
	return _match_config_panel.get_game_mode()


#########################
###     Callbacks     ###
#########################

func _on_start_button_pressed():
	start_button_pressed.emit()


func _on_cancel_button_pressed():
	cancel_pressed.emit()


func _on_replay_select_button_pressed():
	_replay_file_dialog.popup_centered()


func _on_replay_clear_button_pressed():
	ReplayService.clear_prepared_replay()
	_refresh_replay_selection_ui()


func _on_replay_file_dialog_file_selected(path: String):
	var success: bool = ReplayService.prepare_playback(path)
	if !success:
		push_warning("Failed to load replay: %s" % path)
	else:
		print("Loaded replay:", path)

	_refresh_replay_selection_ui()


#########################
###      Private      ###
#########################

func _refresh_replay_selection_ui():
	var has_replay: bool = ReplayService.has_prepared_playback()
	_match_config_panel.set_disabled(has_replay)
	_replay_clear_button.disabled = !has_replay

	if has_replay:
		var meta: Dictionary = ReplayService.get_prepared_replay_meta()
		_replay_summary_label.text = _format_replay_summary(meta)
	else:
		_replay_summary_label.text = "No replay selected."


func _format_replay_summary(meta: Dictionary) -> String:
	var replay_id: String = meta.get("replay_id", "unknown")
	var difficulty_string: String = meta.get("difficulty", "beginner")
	var game_mode_string: String = meta.get("game_mode", "build")
	var wave_count: int = int(meta.get("wave_count", Constants.WAVE_COUNT_TRIAL))
	var created_at: String = meta.get("created_at", "")
	var team_mode_string: String = meta.get("team_mode", "ffa")

	var difficulty: Difficulty.enm = Difficulty.from_string(difficulty_string)
	var difficulty_display: String = Difficulty.convert_to_display_string(difficulty)

	var game_mode: GameMode.enm = GameMode.from_string(game_mode_string)
	var game_mode_display: String = GameMode.convert_to_display_string(game_mode)

	var team_mode: TeamMode.enm = TeamMode.from_string(team_mode_string)
	var team_mode_display: String = TeamMode.convert_to_display_string(team_mode)

	var summary: String = "Replay %s\n%s, %s, %s, Waves: %d" % [replay_id, difficulty_display, game_mode_display, team_mode_display, wave_count]

	if !created_at.is_empty():
		summary += "\nRecorded: %s" % created_at

	return summary

