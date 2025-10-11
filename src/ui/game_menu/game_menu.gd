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
@export var _save_replay_button: Button


func _ready():
	_settings_menu.set_opened_in_game(true)
	_update_save_replay_button_visibility()


func _update_save_replay_button_visibility():
	if _save_replay_button != null:
		# Hide button if we're replaying
		_save_replay_button.visible = !Globals.is_replaying()


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


func _on_encyclopedia_button_pressed() -> void:
	_tab_container.current_tab = Tab.ENCYCLOPEDIA


func _on_encyclopedia_menu_close_pressed() -> void:
	_tab_container.current_tab = Tab.MAIN


func _on_save_replay_button_pressed():
	var recorder: ReplayRecorder = Globals.get_replay_recorder()
	if recorder == null || !recorder.is_recording():
		print("GameMenu: No active replay recording to save")
		return
	
	# Get the replay ID to show user where file is saved
	var replay_id: String = recorder.get_replay_id()
	var replay_path: String = "user://replays/%s.jsonl" % replay_id
	
	print("GameMenu: Replay saved to ", replay_path)
	
	# Show message to user
	var local_player: Player = PlayerManager.get_local_player()
	if local_player != null:
		Messages.add_normal(local_player, "Replay saved: %s" % replay_id)
