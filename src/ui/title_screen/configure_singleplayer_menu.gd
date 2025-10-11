class_name ConfigureSinglePlayerMenu extends PanelContainer


signal cancel_pressed()
signal start_button_pressed()
signal replay_loaded(replay_file_path: String)


@export var _match_config_panel: MatchConfigPanel
@export var _load_replay_button: Button
@export var _replay_file_label: Label

var _selected_replay_file: String = ""


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


#########################
###       Public      ###
#########################

func get_difficulty() -> Difficulty.enm:
	return _match_config_panel.get_difficulty()


func get_game_length() -> int:
	return _match_config_panel.get_game_length()


func get_game_mode() -> GameMode.enm:
	return _match_config_panel.get_game_mode()


func get_selected_replay_file() -> String:
	return _selected_replay_file


func is_replay_mode() -> bool:
	return !_selected_replay_file.is_empty()


#########################
###     Callbacks     ###
#########################

func _on_start_button_pressed():
	start_button_pressed.emit()


func _on_cancel_button_pressed():
	cancel_pressed.emit()


func _on_load_replay_button_pressed():
	var file_dialog = FileDialog.new()
	file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	file_dialog.access = FileDialog.ACCESS_USERDATA
	file_dialog.current_dir = "user://replays"
	file_dialog.add_filter("*.jsonl", "Replay Files")
	
	file_dialog.file_selected.connect(_on_replay_file_selected)
	
	add_child(file_dialog)
	file_dialog.popup_centered(Vector2i(800, 600))


func _on_replay_file_selected(file_path: String):
	_selected_replay_file = file_path
	_replay_file_label.text = file_path.get_file()
	
	# Disable match config panel when replay is loaded
	_match_config_panel.set_disabled(true)
	
	replay_loaded.emit(file_path)
