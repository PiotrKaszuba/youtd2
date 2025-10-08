extends VBoxContainer


enum Tab {
	MAIN = 0,
	HELP,
	ENCYCLOPEDIA,
	SETTINGS,
}


signal continue_pressed()
signal quit_pressed()
signal save_requested(path: String)
signal load_requested(path: String)


@export var _tab_container: TabContainer
@export var _settings_menu: SettingsMenu
@export var _save_dialog: FileDialog
@export var _load_dialog: FileDialog


func _ready():
	_settings_menu.set_opened_in_game(true)
	GameStateSerializer.ensure_default_save_dir()
	var save_dir: String = GameStateSerializer.get_default_save_dir()
	var extension: String = GameStateSerializer.get_default_extension()
	var filter: String = "*%s ; YouTD2 Save" % extension
	_save_dialog.filters = PackedStringArray([filter])
	_load_dialog.filters = PackedStringArray([filter])
	_save_dialog.access = FileDialog.ACCESS_USERDATA
	_load_dialog.access = FileDialog.ACCESS_USERDATA
	_save_dialog.current_dir = save_dir
	_load_dialog.current_dir = save_dir


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


func _on_save_button_pressed():
	_save_dialog.popup_centered()


func _on_load_button_pressed():
	_load_dialog.popup_centered()


func _on_save_dialog_file_selected(path: String):
	save_requested.emit(path)


func _on_load_dialog_file_selected(path: String):
	load_requested.emit(path)
