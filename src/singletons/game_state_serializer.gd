extends Node
class_name GameStateSerializer


const CURRENT_FORMAT_VERSION: int = 1
const DEFAULT_SAVE_DIR: String = "user://saves"
const DEFAULT_EXTENSION: String = ".ytdsave"


var _last_save_error: int = OK


func get_default_save_dir() -> String:
	return DEFAULT_SAVE_DIR


func get_default_extension() -> String:
	return DEFAULT_EXTENSION


func get_last_save_error() -> int:
	return _last_save_error


func ensure_default_save_dir():
	DirAccess.make_dir_recursive_absolute(DEFAULT_SAVE_DIR)


func save_game_scene(game_scene: Node, path: String, metadata: Dictionary = {}) -> int:
	if game_scene == null:
		_last_save_error = ERR_INVALID_PARAMETER
		return _last_save_error

	var normalized_path: String = _normalize_path(path)
	var dir_path: String = normalized_path.get_base_dir()
	if !dir_path.is_empty():
		DirAccess.make_dir_recursive_absolute(dir_path)

	var packed_scene := PackedScene.new()
	var pack_err: int = packed_scene.pack(game_scene)
	if pack_err != OK:
		_last_save_error = pack_err
		return _last_save_error

	var hash_tree: Dictionary = GameStateVerifier.build_hashed_tree_from_scene(game_scene)
	var save_resource := GameStateSave.new()
	save_resource.format_version = CURRENT_FORMAT_VERSION
	save_resource.scene = packed_scene
	save_resource.hash_tree = hash_tree
	save_resource.metadata = metadata

	var save_err: int = ResourceSaver.save(save_resource, normalized_path)
	_last_save_error = save_err

	return save_err


func load_game_scene(path: String) -> int:
	var normalized_path: String = _normalize_path(path)
	if !FileAccess.file_exists(normalized_path):
		return ERR_FILE_NOT_FOUND

	var save_resource: GameStateSave = ResourceLoader.load(normalized_path, "GameStateSave") as GameStateSave
	if save_resource == null:
		return ERR_FILE_CORRUPT

	if save_resource.format_version != CURRENT_FORMAT_VERSION:
		return ERR_INVALID_DATA

	if save_resource.scene == null:
		return ERR_INVALID_DATA

	GameStateVerifier.schedule_expected_hash_tree(save_resource.hash_tree, normalized_path)

	var tree: SceneTree = get_tree()
	tree.paused = false
	var change_err: int = tree.change_scene_to_packed(save_resource.scene)
	return change_err


func _normalize_path(path: String) -> String:
	var trimmed_path: String = path.strip_edges()
	if trimmed_path.is_empty():
		return DEFAULT_SAVE_DIR.path_join("autosave" + DEFAULT_EXTENSION)

	var extension_without_dot: String = DEFAULT_EXTENSION.trim_prefix(".")
	var current_extension: String = trimmed_path.get_extension()
	if current_extension.is_empty():
		return trimmed_path + DEFAULT_EXTENSION

	if current_extension != extension_without_dot:
		return trimmed_path.get_basename() + DEFAULT_EXTENSION

	return trimmed_path
