class_name StateSnapshotter
extends Node


# Builds checksum-tree snapshots for replay verification.


static func compute_root_checksum() -> PackedByteArray:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)

	# Aggregate entity subtree checksums in stable order
	var combined: PackedByteArray = PackedByteArray()

	var towers: Array[Tower] = Utils.get_tower_list()
	towers.sort_custom(_SorterByUid.new(), "sort")
	for tower in towers:
		combined += _checksum_for_tower(tower)

	var creeps: Array[Creep] = Utils.get_creep_list()
	creeps.sort_custom(_SorterByUid.new(), "sort")
	for creep in creeps:
		combined += _checksum_for_creep(creep)

	var items: Array[Node] = get_tree().get_nodes_in_group("items")
	items.sort_custom(_SorterByUid.new(), "sort")
	for item_node in items:
		var item: Item = item_node as Item
		combined += _checksum_for_item(item)

	ctx.update(combined)
	return ctx.finish()


static func build_snapshot_dict() -> Dictionary:
	var out: Dictionary = {}

	var towers_dict: Dictionary = {}
	var tower_list: Array[Tower] = Utils.get_tower_list()
	tower_list.sort_custom(_SorterByUid.new(), "sort")
	for t in tower_list:
		var key: String = "tower:%d@%d,%d" % [t.get_id(), int(t.get_x()), int(t.get_y())]
		var subtree: Dictionary = _collect_tower_state(t)
		towers_dict[key] = subtree

	var creeps_dict: Dictionary = {}
	var creep_list: Array[Creep] = Utils.get_creep_list()
	creep_list.sort_custom(_SorterByUid.new(), "sort")
	for c in creep_list:
		var key_c: String = "creep:%d@%d,%d" % [c.get_uid(), int(c.get_x()), int(c.get_y())]
		creeps_dict[key_c] = _collect_creep_state(c)

	var items_dict: Dictionary = {}
	var item_nodes: Array[Node] = get_tree().get_nodes_in_group("items")
	item_nodes.sort_custom(_SorterByUid.new(), "sort")
	for item_node in item_nodes:
		var it: Item = item_node as Item
		var key_i: String = "item:%d" % it.get_uid()
		items_dict[key_i] = _collect_item_state(it)

	var root_checksum: PackedByteArray = compute_root_checksum()

	out["root"] = ReplayTypes.bytes_to_hex(root_checksum)
	out["towers"] = towers_dict
	out["creeps"] = creeps_dict
	out["items"] = items_dict

	return out


class _SorterByUid:
	func sort(a, b):
		var ua: int = 0
		var ub: int = 0
		if a != null && is_instance_valid(a) && a.has_method("get_uid"):
			ua = a.get_uid()
		if b != null && is_instance_valid(b) && b.has_method("get_uid"):
			ub = b.get_uid()
		return ua < ub


static func _checksum_for_tower(t: Tower) -> PackedByteArray:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	var bytes := PackedByteArray()
	bytes.append(int(t.get_uid()))
	bytes.append(int(t.get_id()))
	bytes.append(int(t.get_level()))
	bytes.append(int(floori(t.get_health())))
	bytes.append(int(floori(t.get_mana())))
	bytes.append(int(floori(t.get_x())))
	bytes.append(int(floori(t.get_y())))
	ctx.update(bytes)
	return ctx.finish()


static func _checksum_for_creep(c: Creep) -> PackedByteArray:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	var bytes := PackedByteArray()
	bytes.append(int(c.get_uid()))
	bytes.append(int(floori(c.get_health())))
	bytes.append(int(floori(c.get_x())))
	bytes.append(int(floori(c.get_y())))
	ctx.update(bytes)
	return ctx.finish()


static func _checksum_for_item(i: Item) -> PackedByteArray:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	var bytes := PackedByteArray()
	bytes.append(int(i.get_uid()))
	bytes.append(int(i.get_id()))
	ctx.update(bytes)
	return ctx.finish()


static func _collect_tower_state(t: Tower) -> Dictionary:
	return {
		"uid": t.get_uid(),
		"id": t.get_id(),
		"level": t.get_level(),
		"hp": int(floori(t.get_health())),
		"mana": int(floori(t.get_mana())),
		"x": int(floori(t.get_x())),
		"y": int(floori(t.get_y())),
	}


static func _collect_creep_state(c: Creep) -> Dictionary:
	return {
		"uid": c.get_uid(),
		"hp": int(floori(c.get_health())),
		"x": int(floori(c.get_x())),
		"y": int(floori(c.get_y())),
	}


static func _collect_item_state(i: Item) -> Dictionary:
	return {
		"uid": i.get_uid(),
		"id": i.get_id(),
	}


