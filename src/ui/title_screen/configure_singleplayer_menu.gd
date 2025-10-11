class_name ConfigureSinglePlayerMenu extends PanelContainer


signal cancel_pressed()
signal start_button_pressed()


@export var _match_config_panel: MatchConfigPanel
var _loaded_replay_path: String = ""


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


#########################
###     Callbacks     ###
#########################

func _on_start_button_pressed():
	start_button_pressed.emit()


func _on_cancel_button_pressed():
	cancel_pressed.emit()


func _on_load_replay_button_pressed():
	var dlg := FileDialog.new()
	dlg.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	dlg.access = FileDialog.ACCESS_USERDATA
	dlg.filters = PackedStringArray(["*.jsonl ; Replay Files"])
	add_child(dlg)
	dlg.popup_centered_ratio(0.6)
	dlg.file_selected.connect(_on_replay_file_selected)


func _on_replay_file_selected(path: String):
	_loaded_replay_path = path
	# Read first line for meta
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("Failed to open replay: %s" % path)
		return
	var meta_line: String = f.get_line()
	f.close()
	var meta: Dictionary = JSON.parse_string(meta_line)
	if typeof(meta) != TYPE_DICTIONARY:
		push_error("Invalid replay meta: %s" % path)
		return
	# Apply settings and grey-out controls
	var settings: Dictionary = meta.get("settings", {})
	if settings.has("game_mode"):
		_match_config_panel.set_game_mode(settings["game_mode"])
	if settings.has("difficulty"):
		_match_config_panel.set_difficulty(settings["difficulty"])
	if settings.has("wave_count"):
		_match_config_panel.set_game_length(settings["wave_count"])
	_match_config_panel.set_disabled(true)
