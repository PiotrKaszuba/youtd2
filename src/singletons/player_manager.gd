extends Node


# Provides global access to players.


signal players_created()


var _id_to_player_map: Dictionary = {}
var _enet_peer_id_to_player_map: Dictionary = {}
var _nakama_user_id_to_player_map: Dictionary = {}
var _player_list: Array[Player] = []


#########################
###       Public      ###
#########################

# Returns player which owns the local game client. In
# singleplayer this is *the player*. In multiplayer, each
# game client has it's own player instance.
# NOTE: "GetLocalPlayer()" in JASS
func get_local_player() -> Player:
	var local_peer_id: int = multiplayer.get_unique_id()
	var local_player: Player = get_player_by_peer_id(local_peer_id)

	return local_player


# NOTE: "Player()" in JASS
func get_player(id: int) -> Player:
	if !_id_to_player_map.has(id):
		push_error("Failed to find player for id ", id)

		return null

	var player: Player = _id_to_player_map[id]

	return player


func get_player_by_peer_id(peer_id: int) -> Player:
	if !_enet_peer_id_to_player_map.has(peer_id):
		push_error("Failed to find player for peer id ", peer_id)

		return null

	var player: Player = _enet_peer_id_to_player_map[peer_id]

	return player


func get_player_by_nakama_user_id(user_id: String) -> Player:
	if !_nakama_user_id_to_player_map.has(user_id):
		push_error("Failed to find player for nakama user id ", user_id)

		return null

	var player: Player = _nakama_user_id_to_player_map[user_id]

	return player


func get_player_list() -> Array[Player]:
	return _player_list.duplicate()


func reset():
	_id_to_player_map = {}
	_enet_peer_id_to_player_map = {}
	_nakama_user_id_to_player_map = {}
	_player_list = []


func get_serialized_state() -> Dictionary:
	var state: Dictionary = {}
	var players: Array = []
	for child in get_children():
		var player: Player = child as Player
		if player == null:
			continue
		var entry: Dictionary = {}
		entry["id"] = player.get_id()
		entry["peer_id"] = player.get_peer_id()
		entry["user_id"] = player.get_user_id()
		players.append(entry)
	state["players"] = players
	return state


func apply_serialized_state(state: Dictionary):
	reset()
	var entries: Array = state.get("players", [])
	var existing: Dictionary = {}
	for child in get_children():
		var player: Player = child as Player
		if player == null:
			continue
		existing[player.get_id()] = player
	for entry in entries:
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var id: int = entry.get("id", -1)
		if !existing.has(id):
			continue
		var player: Player = existing[id]
		var peer_id: int = entry.get("peer_id", -1)
		var user_id: String = entry.get("user_id", "")
		_id_to_player_map[id] = player
		if peer_id != -1:
			_enet_peer_id_to_player_map[peer_id] = player
		player.set("_peer_id", peer_id)
		if !user_id.is_empty():
			_nakama_user_id_to_player_map[user_id] = player
		player.set("_user_id", user_id)
		_player_list.append(player)
	_player_list.sort_custom(
		func(a, b) -> bool:
			return a.get_id() < b.get_id()
	)

func add_player(player: Player):
	var id: int = player.get_id()
	_id_to_player_map[id] = player
	
	var peer_id: int = player.get_peer_id()
	_enet_peer_id_to_player_map[peer_id] = player

	add_child(player)

# 	NOTE: need to sort player id list to ensure determinism in multiplayer
	_player_list.append(player)
	_player_list.sort_custom(
		func(a, b) -> bool:
			return a.get_id() < b.get_id()
			)


func send_players_created_signal():
	players_created.emit()
