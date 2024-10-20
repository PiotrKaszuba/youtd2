class_name CreepMeaty extends BuffType


func _init(parent: Node):
	super("creep_meaty", 0, 0, true, parent)

	add_event_on_death(on_death)


func on_death(event: Event):
	var buff: Buff = event.get_buff()
	var unit: Unit = buff.get_buffed_unit()
	var caster: Unit = event.get_target()

	var creep: Creep = unit as Creep

	if creep == null:
		return

	creep.drop_item_by_id(caster, false, ItemProperties.CONSUMABLE_CHICKEN_ID)
