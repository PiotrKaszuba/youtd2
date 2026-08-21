extends VBoxContainer


enum Tab {
	MAIN = 0,
	HELP,
	ENCYCLOPEDIA,
	SETTINGS,
}


signal continue_pressed()
signal quit_pressed()
signal save_replay_pressed()
signal take_control_pressed()


@export var _tab_container: TabContainer
@export var _settings_menu: SettingsMenu
@export var _encyclopedia_placeholder: PanelContainer
@export var _continue_button: Button
@export var _save_replay_button: Button
@export var _take_control_button: Button

var _encyclopedia_instance: EncyclopediaMenu = null


func _ready():
	_settings_menu.set_opened_in_game(true)


func switch_to_help_menu():
	_tab_container.current_tab = Tab.HELP


func update_replay_controls(mode: ReplayManager.ReplayMode, state: ReplayManager.PlaybackState):
	var is_playback: bool = mode == ReplayManager.ReplayMode.PLAYBACK
	var can_take_control: bool = is_playback && state in [
		ReplayManager.PlaybackState.PLAYING,
		ReplayManager.PlaybackState.PAUSED,
		ReplayManager.PlaybackState.FINISHED,
	]

	_take_control_button.visible = can_take_control
	_save_replay_button.visible = mode == ReplayManager.ReplayMode.RECORDING
	_continue_button.visible = state != ReplayManager.PlaybackState.FINISHED


func _on_continue_button_pressed():
	continue_pressed.emit()


func _on_help_button_pressed():
	_tab_container.current_tab = Tab.HELP


func _on_settings_button_pressed():
	_tab_container.current_tab = Tab.SETTINGS


func _on_hidden():
	_tab_container.current_tab = Tab.MAIN
	
	if _encyclopedia_instance != null:
		_encyclopedia_placeholder.remove_child(_encyclopedia_instance)
		_encyclopedia_instance.queue_free()
		_encyclopedia_instance = null


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
	save_replay_pressed.emit()


func _on_take_control_button_pressed():
	take_control_pressed.emit()


func _on_encyclopedia_button_pressed() -> void:
	_tab_container.current_tab = Tab.ENCYCLOPEDIA
	
	if _encyclopedia_instance == null:
		var encyclopedia_scene: PackedScene = load("res://src/ui/title_screen/encyclopedia_menu.tscn")
		_encyclopedia_instance = encyclopedia_scene.instantiate()
		_encyclopedia_placeholder.add_child(_encyclopedia_instance)
		_encyclopedia_instance.close_pressed.connect(_on_encyclopedia_menu_close_pressed)


func _on_encyclopedia_menu_close_pressed() -> void:
	_tab_container.current_tab = Tab.MAIN
