class_name SnapshotNode
extends RefCounted

var name: String
var _fields: Array = []
var _children: Array[SnapshotNode] = []

var _hash_cache: Dictionary = {}

func _init(node_name: String):
        name = node_name

func add_field(field_name: String, value) -> void:
        _fields.append({"name": field_name, "value": value})
        _hash_cache.clear()

func create_child(child_name: String) -> SnapshotNode:
        var child := SnapshotNode.new(child_name)
        _children.append(child)
        _hash_cache.clear()
        return child

func add_child_node(child: SnapshotNode) -> SnapshotNode:
        _children.append(child)
        _hash_cache.clear()
        return child

func get_children() -> Array[SnapshotNode]:
        return _children.duplicate()

func get_fields() -> Array:
        return _fields.duplicate()

func to_dictionary(include_children: bool = true, include_fields: bool = true) -> Dictionary:
        var result: Dictionary = {"name": name}

        if include_fields:
                var field_dict: Dictionary = {}
                for field in _get_sorted_fields():
                        field_dict[field.name] = _canonicalize_value(field.value)
                result["fields"] = field_dict

        if include_children:
                var child_array: Array = []
                for child in _get_sorted_children():
                        child_array.append(child.to_dictionary(include_children, include_fields))
                result["children"] = child_array

        result["hash"] = get_hash_hex()

        return result

func collect_hashes(path: String = "", include_fields: bool = true, hash_type: int = HashingContext.HASH_SHA256) -> Dictionary:
        var current_path: String = name if path.is_empty() else "%s/%s" % [path, name]
        var result: Dictionary = {current_path: get_hash_hex(hash_type)}

        if include_fields:
                for field in _get_sorted_fields():
                        var field_path: String = "%s.%s" % [current_path, field.name]
                        result[field_path] = _hash_bytes(_encode_value(_canonicalize_value(field.value)), hash_type).hex_encode()

        for child in _get_sorted_children():
                        result.merge(child.collect_hashes(current_path, include_fields, hash_type))

        return result

func get_hash_bytes(hash_type: int = HashingContext.HASH_SHA256) -> PackedByteArray:
        var cache_key := str(hash_type)
        if _hash_cache.has(cache_key):
                return _hash_cache[cache_key]

        var ctx := HashingContext.new()
        ctx.start(hash_type)
        ctx.update(_build_canonical_bytes())
        var hash: PackedByteArray = ctx.finish()
        _hash_cache[cache_key] = hash
        return hash

func get_hash_hex(hash_type: int = HashingContext.HASH_SHA256) -> String:
        return get_hash_bytes(hash_type).hex_encode()

static func write_manual_timer(parent: SnapshotNode, child_name: String, timer: ManualTimer) -> SnapshotNode:
        if timer == null:
                return null

        var child := parent.create_child(child_name)
        child.add_field("wait_time", timer.get_wait_time())
        child.add_field("time_left", timer.get_time_left())
        child.add_field("paused", timer.is_paused())
        child.add_field("stopped", timer.is_stopped())
        child.add_field("one_shot", timer.is_one_shot())
        child.add_field("autostart", timer.has_autostart())
        return child

static func write_timer(parent: SnapshotNode, child_name: String, timer: Timer) -> SnapshotNode:
        if timer == null:
                return null

        var child := parent.create_child(child_name)
        child.add_field("wait_time", timer.wait_time)
        child.add_field("time_left", timer.time_left)
        child.add_field("paused", timer.is_paused())
        child.add_field("stopped", timer.is_stopped())
        child.add_field("one_shot", timer.one_shot)
        child.add_field("autostart", timer.autostart)
        return child

func _build_canonical_bytes() -> PackedByteArray:
        var buffer := PackedByteArray()
        buffer.append_array(_encode_value(name))

        for field in _get_sorted_fields():
                buffer.append_array(_encode_value(field.name))
                buffer.append_array(_encode_value(_canonicalize_value(field.value)))

        for child in _get_sorted_children():
                buffer.append_array(_encode_value(child.name))
                buffer.append_array(child._build_canonical_bytes())

        return buffer

func _get_sorted_fields() -> Array:
        var sorted := _fields.duplicate()
        sorted.sort_custom(func(a, b): return a.name < b.name)
        return sorted

func _get_sorted_children() -> Array[SnapshotNode]:
        var sorted := _children.duplicate()
        sorted.sort_custom(func(a: SnapshotNode, b: SnapshotNode): return a.name < b.name)
        return sorted

static func _canonicalize_value(value):
        match typeof(value):
                TYPE_DICTIONARY:
                        var result: Dictionary = {}
                        var keys: Array = value.keys()
                        keys.sort()
                        for key in keys:
                                result[key] = _canonicalize_value(value[key])
                        return result
                TYPE_ARRAY:
                        var array_result: Array = []
                        for item in value:
                                array_result.append(_canonicalize_value(item))
                        return array_result
                default:
                        return value

static func _encode_value(value) -> PackedByteArray:
        match typeof(value):
                TYPE_ARRAY:
                        var buffer := PackedByteArray()
                        buffer.append_array(var_to_bytes(value.size()))
                        for entry in value:
                                buffer.append_array(_encode_value(entry))
                        return buffer
                TYPE_DICTIONARY:
                        var buffer_dict := PackedByteArray()
                        var keys: Array = value.keys()
                        keys.sort()
                        buffer_dict.append_array(var_to_bytes(keys.size()))
                        for key in keys:
                                buffer_dict.append_array(_encode_value(key))
                                buffer_dict.append_array(_encode_value(value[key]))
                        return buffer_dict
                default:
                        return var_to_bytes(value)

static func _hash_bytes(bytes: PackedByteArray, hash_type: int) -> PackedByteArray:
        var ctx := HashingContext.new()
        ctx.start(hash_type)
        ctx.update(bytes)
        return ctx.finish()
