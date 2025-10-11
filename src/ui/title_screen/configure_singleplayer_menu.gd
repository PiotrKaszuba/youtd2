class_name ConfigureSinglePlayerMenu extends PanelContainer


signal cancel_pressed()
signal start_button_pressed()


@export var _match_config_panel: MatchConfigPanel
@export var _load_replay_button: Button
@export var _replay_file_label: Label
@export var _clear_replay_button: Button

var _selected_replay_path: String = ""
var _replay_metadata: ReplayMetadata = null


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
	
	_update_replay_ui()


#########################
###       Public      ###
#########################

func get_difficulty() -> Difficulty.enm:
	return _match_config_panel.get_difficulty()


func get_game_length() -> int:
	return _match_config_panel.get_game_length()


func get_game_mode() -> GameMode.enm:
	if _replay_metadata != null:
		return _replay_metadata.game_mode
	return _match_config_panel.get_game_mode()


func get_replay_path() -> String:
	return _selected_replay_path


func get_replay_metadata() -> ReplayMetadata:
	return _replay_metadata


#########################
###      Private      ###
#########################

func _update_replay_ui():
	var has_replay: bool = !_selected_replay_path.is_empty()
	
	# Update UI based on whether replay is loaded
	if _clear_replay_button != null:
		_clear_replay_button.visible = has_replay
	
	if _replay_file_label != null:
		if has_replay:
			_replay_file_label.text = "Replay: " + _selected_replay_path.get_file()
			_replay_file_label.show()
		else:
			_replay_file_label.hide()
	
	# Disable settings panel when replay is loaded
	if _match_config_panel != null:
		_match_config_panel.set_process_mode(PROCESS_MODE_DISABLED if has_replay else PROCESS_MODE_INHERIT)
		_match_config_panel.modulate = Color(0.5, 0.5, 0.5) if has_replay else Color(1, 1, 1)


func _load_replay_file(path: String):
	# Load and parse replay metadata
	var replay_player: ReplayPlayer = ReplayPlayer.new()
	var load_success: bool = replay_player.load_replay(path)
	
	if !load_success:
		push_error("ConfigureSinglePlayerMenu: Failed to load replay")
		return
	
	_replay_metadata = replay_player.get_metadata()
	_selected_replay_path = path
	
	# Update match config panel with replay settings
	if _replay_metadata != null:
		_match_config_panel.set_difficulty(_replay_metadata.difficulty)
		_match_config_panel.set_game_mode(_replay_metadata.game_mode)
		_match_config_panel.set_game_length(_replay_metadata.wave_count)
	
	_update_replay_ui()
	
	replay_player.queue_free()


#########################
###     Callbacks     ###
#########################

func _on_start_button_pressed():
	start_button_pressed.emit()


func _on_cancel_button_pressed():
	cancel_pressed.emit()


func _on_load_replay_button_pressed():
	var file_dialog: FileDialog = FileDialog.new()
	add_child(file_dialog)
	
	file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	file_dialog.access = FileDialog.ACCESS_USERDATA
	file_dialog.current_dir = "user://replays"
	file_dialog.add_filter("*.jsonl", "Replay Files")
	file_dialog.title = "Load Replay"
	
	file_dialog.file_selected.connect(func(path: String):
		_load_replay_file(path)
		file_dialog.queue_free()
	)
	
	file_dialog.canceled.connect(func():
		file_dialog.queue_free()
	)
	
	file_dialog.popup_centered(Vector2i(800, 600))


func _on_clear_replay_button_pressed():
	_selected_replay_path = ""
	_replay_metadata = null
	_update_replay_ui()
