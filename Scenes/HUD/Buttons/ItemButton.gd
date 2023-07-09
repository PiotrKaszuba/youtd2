class_name ItemButton 
extends UnitButton

signal right_clicked()


const ICON_SIZE_M = 128

var _item: Item = null : set = set_item, get = get_item

@onready var _cooldown_indicator: CooldownIndicator = $UnitButton/IconContainer/CooldownIndicator


func _ready():
	_set_rarity_icon()
	_set_unit_icon()

	var autocast: Autocast = _item.get_autocast()

	if autocast != null:
		_cooldown_indicator.set_autocast(autocast)
	
	_unit_button.mouse_entered.connect(_on_mouse_entered)
	_unit_button.mouse_exited.connect(_on_mouse_exited)


func _set_rarity_icon():
	set_rarity(ItemProperties.get_rarity(_item.get_id()))


func _set_unit_icon():
	set_unit_icon(ItemProperties.get_icon(_item.get_id()))


func set_item(item: Item):
	_item = item


func get_item() -> Item:
	return _item


func _on_mouse_entered():
	EventBus.item_button_mouse_entered.emit(_item)


func _on_mouse_exited():
	EventBus.item_button_mouse_exited.emit()


func _on_unit_button_right_clicked():
	right_clicked.emit()


func _on_unit_button_pressed():
	var autocast: Autocast = _item.get_autocast()

	if autocast != null:
		autocast.do_cast_if_possible()
