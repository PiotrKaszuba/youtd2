class_name TowerButton
extends UnitButton


@export var _disabled_lock: TextureRect
@export var _tier_icon: TextureRect
@export var _tower_id: int
@export var _freshness_timer: Timer
@export var _freshness_indicator: FreshnessIndicator


#########################
###     Built-in      ###
#########################

func _ready():
	super._ready()
	
	set_locked(false)
	
	_freshness_timer.start()
	
	if !visible:
		_freshness_timer.pause()
	
	_freshness_indicator.show()
	
	var game_mode_is_build: bool = Globals.get_game_mode() == GameMode.enm.BUILD
	if game_mode_is_build:
		_freshness_indicator.hide()


#########################
###       Public      ###
#########################

func get_tower_id() -> int:
	return _tower_id


# NOTE: must be called after button is added to parent
func set_tower_id(tower_id: int):
	_tower_id = tower_id

	var rarity: Rarity.enm = TowerProperties.get_rarity(tower_id)
	set_rarity(rarity)
	
	var tower_icon: Texture2D = TowerProperties.get_icon(tower_id)
	set_icon(tower_icon)
	
	var tier_icon: Texture2D = UnitIcons.get_tower_tier_icon(tower_id)
	_tier_icon.texture = tier_icon


func set_tier_visible(value: bool):
	_tier_icon.visible = value


func set_locked(value: bool):
	_disabled_lock.visible = value
	disabled = value


#########################
###     Callbacks     ###
#########################

func _on_mouse_entered():
	var local_player: Player = PlayerManager.get_local_player()
	var tooltip: String = RichTexts.get_tower_text(_tower_id, local_player)
	ButtonTooltip.show_tooltip(self, tooltip, _tooltip_location)
	
	_freshness_indicator.hide()


#########################
###       Static      ###
#########################

static func make():
	var tower_button: TowerButton = Preloads.tower_button_scene.instantiate()
	return tower_button


# Pause freshness timer while button is not visible
func _on_visibility_changed():
	if _freshness_timer.is_stopped():
		return
	
	_freshness_timer.set_paused(!visible)


func _on_freshness_timer_timeout():
	_freshness_indicator.hide()
