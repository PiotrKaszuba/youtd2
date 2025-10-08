extends Node


# NOTE: singleplayer is also treated as ENET type so there's
# no "NONE" connection
enum ConnectionType {
	ENET,
	NAKAMA
}


# NOTE: these settings are selected during game start. If
# they are accessed before that point, you will get these
# placeholders.
var _player_mode: PlayerMode.enm = PlayerMode.enm.SINGLEPLAYER
var _wave_count: int = 0
var _game_mode: GameMode.enm = GameMode.enm.BUILD
var _difficulty: Difficulty.enm = Difficulty.enm.EASY
var _team_mode: TeamMode.enm = TeamMode.enm.ONE_PLAYER_PER_TEAM
var _origin_seed: int = 0
var _update_ticks_per_physics_tick: int = 1
var _connection_type: ConnectionType = ConnectionType.ENET
var _enet_peer_id_to_player_name: Dictionary = {}
var _title_screen_notification_list: Array[String] = []
var _map: Map = null


# NOTE: you must use random functions via one of the
# RandomNumberGenerator instances below. This is to prevent
# desyncs.
# 
# synced_rng => for deterministic code, which is executed in
# the same way on all multiplayer clients. Examples: picking
# a random damage value, picking a random item.
# 
# local_rng => for non-deterministic code, which is executed
# in a way which is particular to local client. Example:
# random offset for floating text which is visible only to
# local player.
# 
# NOTE: need to use RandomNumberGenerator instead of global
# random functions because it's impossible to keep global
# rng pure. This is because some Godot engine components
# (CPUParticles2D) use global rng and corrupt it.
var synced_rng: RandomNumberGenerator = RandomNumberGenerator.new()
var local_rng: RandomNumberGenerator = RandomNumberGenerator.new()


# NOTE: current variables don't need to be reset. If you add
# some variable which needs to be reset, reset it here.
func reset():
	pass


func get_serialized_state(scene: Node) -> Dictionary:
	var state: Dictionary = {}
	state["player_mode"] = _player_mode
	state["wave_count"] = _wave_count
	state["game_mode"] = _game_mode
	state["difficulty"] = _difficulty
	state["team_mode"] = _team_mode
	state["origin_seed"] = _origin_seed
	state["update_ticks_per_physics_tick"] = _update_ticks_per_physics_tick
	state["connection_type"] = _connection_type
	state["enet_peer_id_to_player_name"] = _enet_peer_id_to_player_name.duplicate(true)
	state["title_screen_notifications"] = _title_screen_notification_list.duplicate()
	state["synced_rng_seed"] = synced_rng.seed
	state["synced_rng_state"] = synced_rng.state
	state["local_rng_seed"] = local_rng.seed
	state["local_rng_state"] = local_rng.state
	var map_path: String = ""
	if scene != null && _map != null && is_instance_valid(_map):
		if scene.is_inside_tree() && _map.is_inside_tree():
			var relative_path: NodePath = scene.get_path_to(_map)
			map_path = String(relative_path)
	state["map_path"] = map_path
	return state


func apply_serialized_state(scene: Node, state: Dictionary):
	_player_mode = state.get("player_mode", _player_mode)
	_wave_count = state.get("wave_count", _wave_count)
	_game_mode = state.get("game_mode", _game_mode)
	_difficulty = state.get("difficulty", _difficulty)
	_team_mode = state.get("team_mode", _team_mode)
	_origin_seed = state.get("origin_seed", _origin_seed)
	_update_ticks_per_physics_tick = state.get("update_ticks_per_physics_tick", _update_ticks_per_physics_tick)
	_connection_type = state.get("connection_type", _connection_type)
	var peer_name_map: Dictionary = state.get("enet_peer_id_to_player_name", {})
	_enet_peer_id_to_player_name = peer_name_map.duplicate(true)
	var notifications: Array = state.get("title_screen_notifications", [])
	_title_screen_notification_list = notifications.duplicate()
	var synced_seed: int = state.get("synced_rng_seed", synced_rng.seed)
	synced_rng.seed = synced_seed
	var synced_state: int = state.get("synced_rng_state", synced_rng.state)
	synced_rng.state = synced_state
	var local_seed: int = state.get("local_rng_seed", local_rng.seed)
	local_rng.seed = local_seed
	var local_state: int = state.get("local_rng_state", local_rng.state)
	local_rng.state = local_state
	var map_path: String = state.get("map_path", "")
	if scene != null && !map_path.is_empty():
		var map_node: Node = scene.get_node_or_null(NodePath(map_path))
		if map_node != null:
			_map = map_node

func get_player_mode() -> PlayerMode.enm:
	return _player_mode


func get_wave_count() -> int:
	return _wave_count


func get_game_mode() -> GameMode.enm:
	return _game_mode


func get_difficulty() -> Difficulty.enm:
	return _difficulty


func get_team_mode() -> TeamMode.enm:
	return _team_mode


func get_origin_seed() -> int:
	return _origin_seed


func game_mode_is_random() -> bool:
	return Globals.get_game_mode() == GameMode.enm.RANDOM_WITH_UPGRADES || Globals.get_game_mode() == GameMode.enm.TOTALLY_RANDOM


func game_mode_allows_transform() -> bool:
	return Globals.get_game_mode() != GameMode.enm.BUILD || Config.allow_transform_in_build_mode()


func game_is_neverending() -> bool:
	return _wave_count == Constants.WAVE_COUNT_NEVERENDING


func get_update_ticks_per_physics_tick() -> int:
	return _update_ticks_per_physics_tick


func set_update_ticks_per_physics_tick(value: int):
	_update_ticks_per_physics_tick = value


func get_connect_type() -> ConnectionType:
	return _connection_type


func get_player_name_from_peer_id(peer_id: int):
	var player_name: String = _enet_peer_id_to_player_name.get(peer_id, "")

	return player_name


func get_map() -> Map:
	return _map


func add_title_screen_notification(text: String):
	_title_screen_notification_list.append(text)


func get_title_screen_notification_list() -> Array[String]:
	return _title_screen_notification_list


func clear_title_screen_notification_list():
	_title_screen_notification_list.clear()

