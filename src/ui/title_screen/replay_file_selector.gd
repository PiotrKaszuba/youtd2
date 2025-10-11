class_name ReplayFileSelector extends VBoxContainer

signal replay_selected(file_path: String)

@export var _file_list: ItemList
@export var _load_button: Button


func _ready():
	_refresh_file_list()


func _refresh_file_list():
	_file_list.clear()

	# Get replay files from ReplayManager
	var replay_manager: ReplayManager = get_node("/root/ReplayManager") if get_tree().root.has_node("ReplayManager") else null

	if replay_manager:
		var replays: Array = replay_manager.get_replay_list()

		for replay_info in replays:
			var timestamp: String = Time.get_datetime_string_from_unix_time(replay_info.get("timestamp", 0))
			var display_name: String = "%s - %s waves - %s" % [
				timestamp,
				replay_info.get("wave_count", 0),
				Difficulty.convert_to_colored_string(replay_info.get("difficulty", 0))
			]

			_file_list.add_item(display_name)
			_file_list.set_item_metadata(_file_list.get_item_count() - 1, replay_info.get("replay_id", ""))


func _on_file_list_item_selected(index: int):
	var file_path: String = _file_list.get_item_metadata(index)
	_load_button.disabled = file_path.is_empty()


func get_selected_replay_id() -> String:
	var selected_items: Array = _file_list.get_selected_items()
	if selected_items.is_empty():
		return ""

	var index: int = selected_items[0]
	return _file_list.get_item_metadata(index)


func _on_load_button_pressed():
	var selected_items: Array = _file_list.get_selected_items()
	if selected_items.is_empty():
		return

	var index: int = selected_items[0]
	var file_path: String = _file_list.get_item_metadata(index)

	if !file_path.is_empty():
		replay_selected.emit(file_path)


func _on_refresh_button_pressed():
	_refresh_file_list()
