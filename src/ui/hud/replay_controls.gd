extends Control


# UI controls shown during replay playback


@export var _speed_normal_button: Button
@export var _speed_fast_button: Button
@export var _speed_fastest_button: Button
@export var _progress_label: Label

var _replay_player: ReplayPlayer = null


#########################
###     Built-in      ###
#########################

func _ready():
	hide()  # Hidden by default, shown when replay starts


func _process(_delta: float):
	if _replay_player != null && _replay_player.is_playing():
		_update_progress_display()


#########################
###       Public      ###
#########################

func set_replay_player(player: ReplayPlayer):
	_replay_player = player
	if _replay_player != null:
		_replay_player.replay_finished.connect(_on_replay_finished)
		_replay_player.replay_progress_updated.connect(_on_replay_progress_updated)
		show()


#########################
###      Private      ###
#########################

func _update_progress_display():
	if _replay_player == null || _progress_label == null:
		return
	
	var current_tick: int = _replay_player.get_current_tick()
	var total_ticks: int = _replay_player.get_total_ticks()
	
	# Convert ticks to seconds (30 ticks per second)
	var current_seconds: float = current_tick / 30.0
	var total_seconds: float = total_ticks / 30.0
	
	var current_time_str: String = _format_time(current_seconds)
	var total_time_str: String = _format_time(total_seconds)
	
	_progress_label.text = "Replay: %s / %s" % [current_time_str, total_time_str]


func _format_time(seconds: float) -> String:
	var minutes: int = int(seconds) / 60
	var secs: int = int(seconds) % 60
	return "%d:%02d" % [minutes, secs]


#########################
###     Callbacks     ###
#########################

func _on_speed_normal_pressed():
	Globals.set_update_ticks_per_physics_tick(Constants.GAME_SPEED_NORMAL)


func _on_speed_fast_pressed():
	Globals.set_update_ticks_per_physics_tick(Constants.GAME_SPEED_FAST)


func _on_speed_fastest_pressed():
	Globals.set_update_ticks_per_physics_tick(Constants.GAME_SPEED_FASTEST)


func _on_replay_finished():
	hide()


func _on_replay_progress_updated(_current_tick: int, _total_ticks: int):
	_update_progress_display()

