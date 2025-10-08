extends Node
#class_name GameStateSerializer


const AutoloadStateSerializer = preload("res://src/game_state/autoload_state_serializer.gd")

const CURRENT_FORMAT_VERSION: int = 1
const DEFAULT_SAVE_DIR: String = "user://saves"
const SAVE_SCENE_EXTENSION = ".tscn"
const SAVE_META_EXTENSION = ".meta"


var _last_save_error: int = OK
var _pending_autoload_state: Dictionary = {}


func get_default_save_dir() -> String:
	return DEFAULT_SAVE_DIR

func get_scene_extension() -> String:
	return SAVE_SCENE_EXTENSION

func get_meta_extension() -> String:
	return SAVE_META_EXTENSION

func get_last_save_error() -> int:
	return _last_save_error


func ensure_default_save_dir():
	DirAccess.make_dir_recursive_absolute(DEFAULT_SAVE_DIR)


func save_game_scene(game_scene: Node, path: String, metadata: Dictionary = {}) -> int:
	if game_scene == null:
		_last_save_error = ERR_INVALID_PARAMETER
		return _last_save_error

	var normalized_scene_path: String = _normalize_path(path, SAVE_SCENE_EXTENSION)
	var normalized_meta_path: String = _normalize_path(path, SAVE_META_EXTENSION)
	var dir_path: String = normalized_scene_path.get_base_dir()
	if !dir_path.is_empty():
		DirAccess.make_dir_recursive_absolute(dir_path)

	var packed_scene := PackedScene.new()
	var pack_err: int = packed_scene.pack(game_scene)
	if pack_err != OK:
		_last_save_error = pack_err
		return _last_save_error

	var hash_tree: Dictionary = GameStateVerifier.build_hashed_tree_from_scene(game_scene)
	var meta_dict: Dictionary = {
		"format_version": CURRENT_FORMAT_VERSION,
		"hash_tree": hash_tree,
		"metadata": metadata,
		"autoload_state": AutoloadStateSerializer.capture_state(game_scene),
	}

	var save_err: int = ResourceSaver.save(packed_scene, normalized_scene_path)
	_last_save_error = save_err
	if save_err != OK:
		return save_err

	var meta_file := FileAccess.open(normalized_meta_path, FileAccess.WRITE)
	if meta_file == null:
			return FileAccess.get_open_error()

	meta_file.store_var(meta_dict, false)
	meta_file.close()

	return save_err


func load_game_scene(path: String) -> int:
	var normalized_scene_path: String = _normalize_path(path, SAVE_SCENE_EXTENSION)
	var normalized_meta_path: String = _normalize_path(path, SAVE_META_EXTENSION)
	if !FileAccess.file_exists(normalized_scene_path) or !FileAccess.file_exists(normalized_meta_path):
		return ERR_FILE_NOT_FOUND

	var packed_scene: PackedScene = ResourceLoader.load(normalized_scene_path, "PackedScene") as PackedScene
	if packed_scene == null:
		return ERR_FILE_CORRUPT

	var meta_file := FileAccess.open(normalized_meta_path, FileAccess.READ)
	if meta_file == null:
		return FileAccess.get_open_error()

	var meta_dict: Dictionary = meta_file.get_var(false)
	meta_file.close()
	if typeof(meta_dict) != TYPE_DICTIONARY:
		return ERR_FILE_CORRUPT

	if meta_dict.get("format_version", 0) != CURRENT_FORMAT_VERSION:
		return ERR_INVALID_DATA

	if meta_dict.get("hash_tree") == null:
		return ERR_INVALID_DATA

	_pending_autoload_state = meta_dict.get("autoload_state", {}).duplicate(true)
	GameStateVerifier.schedule_expected_hash_tree(meta_dict.get("hash_tree", {}), normalized_scene_path)

	var tree: SceneTree = get_tree()
	tree.paused = false
	var change_err: int = tree.change_scene_to_packed(packed_scene)
	return change_err


func consume_pending_autoload_state() -> Dictionary:
	var state: Dictionary = _pending_autoload_state.duplicate(true)
	_pending_autoload_state = {}
	return state


func _normalize_path(path: String, extension: String) -> String:
	var trimmed_path: String = path.strip_edges()
	if trimmed_path.is_empty():
		return DEFAULT_SAVE_DIR.path_join("autosave" + extension)

	var extension_without_dot: String = extension.trim_prefix(".")
	var current_extension: String = trimmed_path.get_extension()
	if current_extension.is_empty():
		return trimmed_path + extension

	if current_extension != extension_without_dot:
		return trimmed_path.get_basename() + extension

	return trimmed_path
