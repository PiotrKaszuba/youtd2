class_name ReplayTypes


# Central constants and helpers for replay system.


const REPLAY_DIR: String = "user://replays"
const STATE_DIR_NAME: String = "_state"
const SCHEMA_VERSION: int = 1


static func get_replay_file_path(replay_id: String) -> String:
	return "%s/%s.jsonl" % [REPLAY_DIR, replay_id]


static func get_state_dir_path() -> String:
	return "%s/%s" % [REPLAY_DIR, STATE_DIR_NAME]


static func get_state_file_path(replay_id: String, tick: int) -> String:
	return "%s/%s-%d.json" % [get_state_dir_path(), replay_id, tick]


static func ensure_dirs_exist():
	DirAccess.make_dir_recursive_absolute(REPLAY_DIR)
	DirAccess.make_dir_recursive_absolute(get_state_dir_path())


static func bytes_to_hex(bytes: PackedByteArray) -> String:
	var hex: String = ""
	for b in bytes:
		hex += "%02x" % int(b)
	return hex


static func action_is_loggable(action: Dictionary) -> bool:
	if !action.has(Action.Field.TYPE):
		return false

	var t: int = action[Action.Field.TYPE]
	# Exclude purely UI-only or cosmetic actions from logs.
	# Keep chat and all state-changing actions.
	match t:
		Action.Type.SELECT_UNIT:
			return false
		Action.Type.SORT_ITEM_STASH:
			return false
		Action.Type.SET_PLAYER_NAME:
			return false
		_:
			return true


