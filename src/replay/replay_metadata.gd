class_name ReplayMetadata


# Stores metadata about a replay, including initial game state
# and information needed to restore the exact scenario.


# Initial game settings
var origin_seed: int = 0
var difficulty: Difficulty.enm = Difficulty.enm.EASY
var game_mode: GameMode.enm = GameMode.enm.RANDOM_WITH_UPGRADES
var wave_count: int = 0
var team_mode: TeamMode.enm = TeamMode.enm.ONE_PLAYER_PER_TEAM
var player_mode: PlayerMode.enm = PlayerMode.enm.SINGLEPLAYER

# Player settings at game start
var exp_password: String = ""
var wisdom_upgrades: Dictionary = {}
var builder_id: int = 0

# Replay metadata
var replay_id: String = ""
var timestamp: int = 0
var game_version: String = ""
var total_ticks: int = 0

# List of ticks where checksum snapshots exist
var checkpoint_ticks: Array[int] = []


#########################
###       Public      ###
#########################

func to_dict() -> Dictionary:
	return {
		"origin_seed": origin_seed,
		"difficulty": Difficulty.convert_to_string(difficulty),
		"game_mode": GameMode.convert_to_string(game_mode),
		"wave_count": wave_count,
		"team_mode": TeamMode.convert_to_string(team_mode),
		"player_mode": PlayerMode.convert_to_string(player_mode),
		"exp_password": exp_password,
		"wisdom_upgrades": wisdom_upgrades,
		"builder_id": builder_id,
		"replay_id": replay_id,
		"timestamp": timestamp,
		"game_version": game_version,
		"total_ticks": total_ticks,
		"checkpoint_ticks": checkpoint_ticks,
	}


static func from_dict(data: Dictionary) -> ReplayMetadata:
	var metadata: ReplayMetadata = ReplayMetadata.new()
	
	metadata.origin_seed = data.get("origin_seed", 0)
	metadata.difficulty = Difficulty.from_string(data.get("difficulty", "easy"))
	metadata.game_mode = GameMode.from_string(data.get("game_mode", "random"))
	metadata.wave_count = data.get("wave_count", 0)
	metadata.team_mode = TeamMode.from_string(data.get("team_mode", "one"))
	metadata.player_mode = PlayerMode.from_string(data.get("player_mode", "single"))
	metadata.exp_password = data.get("exp_password", "")
	metadata.wisdom_upgrades = data.get("wisdom_upgrades", {})
	metadata.builder_id = data.get("builder_id", 0)
	metadata.replay_id = data.get("replay_id", "")
	metadata.timestamp = data.get("timestamp", 0)
	metadata.game_version = data.get("game_version", "")
	metadata.total_ticks = data.get("total_ticks", 0)
	
	var checkpoint_ticks_variant: Array = data.get("checkpoint_ticks", [])
	metadata.checkpoint_ticks = []
	for tick in checkpoint_ticks_variant:
		metadata.checkpoint_ticks.append(tick as int)
	
	return metadata


# Generate a unique replay ID based on initial state and timestamp
static func generate_replay_id(metadata: ReplayMetadata) -> String:
	var state_string: String = "%d_%d_%d_%d_%d" % [
		metadata.origin_seed,
		metadata.difficulty,
		metadata.game_mode,
		metadata.wave_count,
		metadata.timestamp
	]
	
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(state_string.to_utf8_buffer())
	var hash: PackedByteArray = ctx.finish()
	
	# Convert to hex string (first 16 chars for readability)
	var hex_string: String = hash.hex_encode().substr(0, 16)
	
	return hex_string

