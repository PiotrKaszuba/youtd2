class_name Action


# Wraps Dictionary which needs to be passed through RPC.
# Need to pass Dictionaries through RPC because Godot RPC
# doesn't support passing custom classes.
# 
# Parameters -> Action:
#     var action: Action = ActionFoo.make(bar, baz)
#
# Action -> Dictionary:
#     var serialized_action: Dictionary = action.serialize()


enum Field {
	TYPE,
	PLAYER_ID,
	CHAT_MESSAGE,
	TOWER_ID,
	POSITION,
	UID,
	UID_2,
	UID_LIST,
	BUILDER_ID,
	SRC_ITEM_CONTAINER_UID,
	DEST_ITEM_CONTAINER_UID,
	CLICKED_INDEX,
	BUFFGROUP,
	BUFFGROUP_MODE,
	ELEMENT,
	WISDOM_UPGRADES,
}

enum Type {
	NONE,
	IDLE,
	CHAT,
	SET_PLAYER_NAME,
	BUILD_TOWER,
	UPGRADE_TOWER,
	TRANSFORM_TOWER,
	SELL_TOWER,
	SELECT_BUILDER,
	SELECT_WISDOM_UPGRADES,
	TOGGLE_AUTOCAST,
	CONSUME_ITEM,
	DROP_ITEM,
	MOVE_ITEM,
	SWAP_ITEMS,
	AUTOFILL,
	TRANSMUTE,
	RESEARCH_ELEMENT,
	ROLL_TOWERS,
	START_NEXT_WAVE,
	AUTOCAST,
	FOCUS_TARGET,
	CHANGE_BUFFGROUP,
	SELECT_UNIT,
	SORT_ITEM_STASH,
}


var _data: Dictionary


#########################
###     Built-in      ###
#########################

func _init(data: Dictionary):
	_data = data


#########################
###       Public      ###
#########################

func serialize() -> Dictionary:
	return _data


# Exclude UI-only actions and other non-gameplay actions
static var excluded_types: Array = [
		Type.IDLE,
		Type.SELECT_UNIT,
		Type.SELECT_WISDOM_UPGRADES,
]

static func is_replayable_type(type: Type):
	return not (type in Action.excluded_types)

func is_replayable() -> bool:
	"""Check if this action should be included in replays"""

	var action_type: Type = get_type()
	return Action.is_replayable_type(action_type)


func get_type() -> Type:
	"""Get the action type"""
	return _data.get(Field.TYPE, Type.NONE)
