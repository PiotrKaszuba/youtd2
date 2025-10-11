extends VBoxContainer


enum Tab {
	MAIN = 0,
	HELP,
	ENCYCLOPEDIA,
	SETTINGS,
}


signal continue_pressed()
signal quit_pressed()


@export var _tab_container: TabContainer
@export var _settings_menu: SettingsMenu


func _ready():
	_settings_menu.set_opened_in_game(true)


func switch_to_help_menu():
	_tab_container.current_tab = Tab.HELP


func _on_continue_button_pressed():
	continue_pressed.emit()


func _on_help_button_pressed():
	_tab_container.current_tab = Tab.HELP


func _on_settings_button_pressed():
	_tab_container.current_tab = Tab.SETTINGS


func _on_hidden():
	_tab_container.current_tab = Tab.MAIN


func _on_help_menu_closed():
	_tab_container.current_tab = Tab.MAIN


func _on_help_menu_hidden():
	_tab_container.current_tab = Tab.MAIN


func _on_settings_menu_cancel_pressed():
	_tab_container.current_tab = Tab.MAIN


func _on_settings_menu_ok_pressed():
	_tab_container.current_tab = Tab.MAIN


func _on_quit_button_pressed():
	quit_pressed.emit()


func _on_save_replay_button_pressed():
	# Only available in singleplayer; host owns recorder
	var is_singleplayer: bool = Globals.get_player_mode() == PlayerMode.enm.SINGLEPLAYER
	if !is_singleplayer:
		Utils.add_ui_error(PlayerManager.get_local_player(), "Replay saving is singleplayer-only in v1")
		return

	var host: GameHost = get_tree().get_root().get_node_or_null("GameScene/Gameplay/GameHost")
	if host == null:
		push_error("GameHost not found; cannot save replay")
		return

	# Recorder writes continuously; ensure flush to disk now
	if host.has_method("_replay_recorder"):
		# Access via property; fallback is no-op if unavailable
		var recorder = host._replay_recorder
		if recorder != null && recorder.has_method("close"):
			recorder.close()
			Utils.add_ui_error(PlayerManager.get_local_player(), "Replay saved to user://replays/")


func _on_encyclopedia_button_pressed() -> void:
	_tab_container.current_tab = Tab.ENCYCLOPEDIA


func _on_encyclopedia_menu_close_pressed() -> void:
	_tab_container.current_tab = Tab.MAIN
