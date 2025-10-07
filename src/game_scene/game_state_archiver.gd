class_name GameStateArchiver
extends RefCounted

const SAVE_DIR := "user://saves"
const SAVE_SCENE_PATH := SAVE_DIR + "/latest.tscn"
const SAVE_META_PATH := SAVE_DIR + "/latest.meta"
const FORMAT_VERSION := 1

static func save(game_scene: GameScene, snapshot_root: SnapshotNode, hash_type: int) -> Error:
        var dir_error: Error = DirAccess.make_dir_recursive_absolute(SAVE_DIR)
        if dir_error != OK and dir_error != ERR_ALREADY_EXISTS:
                return dir_error

        var packed_scene := PackedScene.new()
        var pack_error: Error = packed_scene.pack(game_scene)
        if pack_error != OK:
                return pack_error

        var save_error: Error = ResourceSaver.save(packed_scene, SAVE_SCENE_PATH)
        if save_error != OK:
                return save_error

        var snapshot_parts: Dictionary = snapshot_root.collect_hashes("", true, hash_type)
        var rng := Globals.synced_rng
        var rng_state = null
        var rng_position = null
        var rng_call_count = null

        if rng.has_method("get_state"):
                rng_state = rng.get_state()
        if rng.has_method("get_position"):
                rng_position = rng.get_position()
        if rng.has_method("get_call_count"):
                rng_call_count = rng.get_call_count()

        var meta: Dictionary = {
                "format_version": FORMAT_VERSION,
                "hash_type": hash_type,
                "tick": game_scene.get_current_tick(),
                "snapshot_hash": snapshot_root.get_hash_hex(hash_type),
                "snapshot_parts": snapshot_parts,
                "saved_at": Time.get_datetime_string_from_system(),
                "rng_state": rng_state,
                "rng_position": rng_position,
                "rng_call_count": rng_call_count,
        }

        var meta_file := FileAccess.open(SAVE_META_PATH, FileAccess.WRITE)
        if meta_file == null:
                return FileAccess.get_open_error()

        meta_file.store_var(meta, false)
        meta_file.close()

        return OK

static func load(tree: SceneTree) -> Error:
        if !FileAccess.file_exists(SAVE_SCENE_PATH) or !FileAccess.file_exists(SAVE_META_PATH):
                return ERR_FILE_NOT_FOUND

        var meta_file := FileAccess.open(SAVE_META_PATH, FileAccess.READ)
        if meta_file == null:
                return FileAccess.get_open_error()

        var meta := meta_file.get_var(false)
        meta_file.close()
        if typeof(meta) != TYPE_DICTIONARY:
                return ERR_PARSE_ERROR

        var resource := ResourceLoader.load(SAVE_SCENE_PATH)
        var packed_scene: PackedScene = resource as PackedScene
        if packed_scene == null:
                return ERR_INVALID_DATA

        var new_scene := packed_scene.instantiate()
        if new_scene == null:
                return ERR_CANT_CREATE
        var game_scene := new_scene as GameScene
        if game_scene != null:
                game_scene.begin_restore(meta)

        var root := tree.get_root()
        var old_scene := tree.current_scene

        if old_scene != null:
                old_scene.queue_free()

        root.add_child(new_scene)
        tree.current_scene = new_scene

        return OK
