class_name PlayerMode extends Node


enum enm {
	SINGLEPLAYER,
	MULTIPLAYER,
}


static func convert_to_string(player_mode: PlayerMode.enm) -> String:
	match player_mode:
		PlayerMode.enm.SINGLEPLAYER:
			return "single"
		PlayerMode.enm.MULTIPLAYER:
			return "multi"
		_:
			return "single"


static func from_string(string: String) -> PlayerMode.enm:
	match string:
		"single":
			return PlayerMode.enm.SINGLEPLAYER
		"multi":
			return PlayerMode.enm.MULTIPLAYER
		_:
			return PlayerMode.enm.SINGLEPLAYER
