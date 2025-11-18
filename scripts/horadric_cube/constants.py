from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias, Dict, List, Optional, Tuple

import numpy as np
from pathlib import Path

ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent
DATA_DIR: Path = ROOT_DIR / "data"
ITEM_PROPERTIES_FILE: Path = DATA_DIR / "item_properties.csv"
RECIPE_PROPERTIES_FILE: Path = DATA_DIR / "recipe_properties.csv"

Inventory = Dict[int, int]

GAME_PHASE: TypeAlias = int  # phase index: 0, 1, 2, ...
WAVE_LEVEL: TypeAlias = int
ITEM_ID: TypeAlias = int
GAME_PHASE_VALUE: TypeAlias = float
GAME_PHASE_VALUE_DICT: TypeAlias = Dict[GAME_PHASE, GAME_PHASE_VALUE]


# Game phases defined by upper wave-level thresholds.
# Phase indices are 0..len(GAME_PHASES)-1; the numeric thresholds are used
# only when we need actual level values.
GAME_PHASES: List[float] = [
	8, 24, 48, 80, 120, 180, 260, 350, np.inf
]


def get_game_phase_index(level: WAVE_LEVEL) -> GAME_PHASE:
	"""
	Return the phase index for a given wave level.

	Phase 0 covers levels <= GAME_PHASES[0], phase 1 covers levels between
	GAME_PHASES[0] and GAME_PHASES[1], etc.
	"""
	for i, phase_level in enumerate(GAME_PHASES):
		if level <= phase_level:
			return i
	return len(GAME_PHASES) - 1  # index of last phase


@dataclass(frozen=True)
class ItemValue:
	item_id: ITEM_ID
	usage_value: GAME_PHASE_VALUE_DICT
	transmute_value: GAME_PHASE_VALUE_DICT  # learned later

	@staticmethod
	def from_data(
		item_id: ITEM_ID,
		usage_value: GAME_PHASE_VALUE_DICT = None,
		inventory: Optional[Inventory] = None,
		usage_caps: Optional[Dict[ITEM_ID, Tuple[int, GAME_PHASE_VALUE]]] = None,
	) -> ItemValue:
		"""
		Build an ItemValue from sparse usage_value data.

		- usage_value may contain a base value at key -1 and optional per-phase
		  overrides keyed by phase index.
		- If inventory and usage_caps are provided and the inventory already
		  contains at least max_count copies of this item, usage values are
		  collapsed to the configured overflow value (default 0.0 when not set).
		"""
		if usage_value is None:
			usage_value = {phase: 0.0 for phase in range(len(GAME_PHASES))}
		else:
			# take copy to avoid modifying the original
			usage_value = usage_value.copy()

		# get and remove base value (applied to all phases)
		base_usage_value = usage_value.pop(-1, 0.0)

		usage_value_full = {
			phase_idx: base_usage_value + usage_value.get(phase_idx, 0.0)
			for phase_idx in range(len(GAME_PHASES))
		}

		# Apply inventory-aware caps if requested.
		if inventory is not None and usage_caps is not None:
			count = inventory.get(item_id, 0)
			max_count, overflow_val = usage_caps.get(item_id, (None, 0.0))
			if max_count is not None and count >= max_count:
				usage_value_full = {phase_idx: overflow_val for phase_idx in range(len(GAME_PHASES))}

		transmute_value_full = {phase_idx: 0.0 for phase_idx in range(len(GAME_PHASES))}
		return ItemValue(item_id, usage_value_full, transmute_value_full)

	# value is the maximum of usage value and transmute value for a given phase index
	def get_value(self, game_phase: GAME_PHASE) -> GAME_PHASE_VALUE:
		return max(self.usage_value.get(game_phase, 0.0), self.transmute_value.get(game_phase, 0.0))



# Recipe IDs matching recipe_properties.csv and HoradricCube.Recipe enum.
RECIPE_NONE: int = 0
RECIPE_REBREW: int = 1
RECIPE_DISTILL: int = 2
RECIPE_REASSEMBLE: int = 3
RECIPE_PERFECT: int = 4
RECIPE_LIQUEFY: int = 5
RECIPE_PRECIPITATE: int = 6
RECIPE_IMBUE: int = 7


# Commonly referenced item IDs for convenience in analyses.
ENCHANTED_MINING_PICK: int = 8
HAUNTED_HAND: int = 246

# COMMON ITEMS

RUSTY_MINING_PICK: int = 99
VOID_VIAL: int = 75
ASSASINATION_ARROW: int = 277
TRAINING_MANUAL: int = 135
YOUNG_THIEF_CLOAK: int = 160
SKULL_TROPHY: int = 163
RING_OF_LUCK: int = 153
SCARAB_AMULET: int = 168
OLD_CRYSTAL_BALL: int = 104
MAGIC_GLOVES: int = 271
SPIDER_SILK: int = 106
LAND_MINE: int = 11
SCROLL_OF_MYTHS: int = 29
NINJA_GLAIVE: int = 16
BOMB_SHELLS: int = 33
MAGICAL_ESSENCE: int = 12
ORC_WAR_SPEAR: int = 21
ELEGANT_RING: int = 234
MINI_SHEEP: int = 37
PIECE_OF_MEAT: int = 39
TOOTH_TROPHY: int = 164
CLAWS_OF_ATTACK: int = 2
GARGOYLE_WING: int = 40
HEAVY_CROSSBOW: int = 189
PIRATE_MAP: int = 38
TROLL_VOODOO_MASK: int = 107
SHIMMERWEED: int = 91
GIFT_OF_THE_WILD: int = 93
RAILGUN: int = 173
RUNED_WOOD: int = 176
MINING_LAMP: int = 94
ELECTRIFIED_HORSESHOE: int = 57
INSCRIBED_PEBBLE: int = 92
ENCHANTED_BIRD_FIGURINE: int = 157
SACRED_HALO: int = 172

STRANGE_ITEM: int = 233

# UNCOMMON ITEMS

VULSHOK_S_CLAWS: int = 3
DRAGON_S_HEART: int = 4
ARCHER_S_HOOD: int = 5
WIZARD_STAFF: int = 6
HEAVY_GUN: int = 7
SURVIVAL_KIT: int = 19
COMBAT_GLOVES: int = 20
MOONSILVER_CIRCLET: int = 24
CRYSTAL_STAFF: int = 25
LIGHTNING_BOOTS: int = 26
CLAWS_OF_THE_BEAR: int = 27
CEREMONIAL_SKULL: int = 28
TOME_OF_SHADOW_MAGIC: int = 30
ZOMBIE_HAND: int = 31
HAND_OF_RUIN: int = 34
ANCIENT_FIGURINE: int = 41
WINE_OF_ALUQAH: int = 43
MASK_OF_SANITY: int = 44
MINDS_KEY: int = 46
BATTLE_SUIT: int = 51
ZOMBIE_HEAD: int = 52
MORGUL_SLAVE: int = 53
TINY_RABBIT: int = 54
FLAMING_ARROW: int = 55
MAGIC_VIAL: int = 63
AXE_OF_DECAPITATION: int = 74
CLAWS_OF_WISDOM: int = 77
PILLAGE_TOOLS: int = 81
TOUCH_OF_A_SPIRIT: int = 82
PERISCOPE: int = 83
ANCIENT_INSCRIBED_BARK: int = 84
BLESSED_HOLY_SCEPTER: int = 85
BLUNDERBUSS_RIFLE: int = 86
THICK_TREE_BRANCH: int = 87
UNDEAD_SPIKED_CLAWS: int = 88
HUNTING_MAP: int = 90
VOODOO_DOLL: int = 95
SPIKED_CLUB: int = 96
MINI_TANK: int = 97
ARCANE_EYE: int = 100
POLARISATOR: int = 102
EXPANDING_MIND: int = 108
MAGIC_FLOWER: int = 109
MARK_OF_THE_TALON: int = 110
MARK_OF_THE_CLAW: int = 111
FLAWLESS_SAPPHIRE: int = 112
SUPPORT_COLUMN: int = 114
OBSIDIAN_FIGURINE: int = 115
SHADOWFOOT_S_MANTLE: int = 116
BLOOD_CROWN: int = 117
SAGE_S_MASK: int = 118
KNOWING_MIND: int = 119
TROLL_CHARM: int = 123
SCROLL_OF_PIERCING_MAGIC: int = 124
MYSTICAL_SHELL: int = 125
DUMPSTER: int = 128
BEAST_HEAD: int = 134
GRAND_SEAL_OF_PICKINESS: int = 136
DIAMOND_OF_GREED: int = 139
MAGICIAN_S_DOORKEY: int = 141
WANTED_LIST: int = 144
SHINY_EMERALD: int = 145
NAGA_TRIDENT: int = 148
PANDA_DRESS: int = 150
WISE_MAN_S_COOKING_RECIPE: int = 151
MINING_TOOLS: int = 158
CHARGED_DISK: int = 159
CRYSTALLIZED_SCALES: int = 170
TOXIC_CHEMICALS: int = 175
SPIDER_BROACH: int = 182
OGRE_STAFF_OF_WISDOM: int = 187
DEMONIC_ORB: int = 190
SPEED_DEMON_S_REWARD: int = 191
DEEP_SHADOWS: int = 192
BONES_OF_ESSENCE: int = 194
AQUEOUS_VAPOR: int = 195
GLOWING_GAUNTLETS: int = 196
DOWSING_ROD: int = 199
SPARKLING_STAFF: int = 204
ORB_OF_SOULS: int = 210
BLOODTHIRSTY_AXE: int = 211
BLASTER_STAFF: int = 218
ENCHANTED_TELESCOPE: int = 219
IRON_LEG: int = 223
MASTER_THIEF_S_SHROUD: int = 224
FIERY_ASSASSINATION_ARROW: int = 225
UNSTABLE_CURRENT: int = 226
RAZOR_SHARP_DAGGER: int = 229
RING_OF_CHANCE: int = 232
HERMIT_STAFF: int = 235
VETERAN_S_TOME_OF_BATTLE: int = 236
MONOCLE: int = 243
DRAGON_CLAWS: int = 256
SHRAPNEL_AMMUNITION: int = 257
QUICKTRIGGER_BLADE: int = 259
OGRE_BATTLE_AXE: int = 263
MAGIC_LINK: int = 265
UNYIELDING_MAUL: int = 280


# -1 is a special GAME_PHASE to be used as base value for all game phases
USAGE_ITEM_VALUES: Dict[ITEM_ID, GAME_PHASE_VALUE_DICT] = {
	# ENCHANTED_MINING_PICK: {-1: 1.0}

	## ITEM FIND  / QUALITY
	# Common items
	RUSTY_MINING_PICK: {0: 0.1, 1: 0.1, 2: 0.05},
	YOUNG_THIEF_CLOAK: {0: 0.25, 1: 0.25, 2: 0.25, 3: 0.1,},
	OLD_CRYSTAL_BALL: {0: 0.25, 1: 0.25, 2: 0.25, 3: 0.1,},
	PIRATE_MAP: {0: 0.5, 1: 0.5, 2: 0.35, 3: 0.25, 4: 0.1, 5: 0.05,},
	RUNED_WOOD: {-1: 0.35, 4: -0.1, 5: -0.15, 6: -0.25, 7: -0.35, 8: -0.35},
	MINING_LAMP: {-1: 1.0, 6: -0.25, 7: -0.75, 8: -1.0},

	# Uncommon items
	TINY_RABBIT: {0: 0.1, 1: 0.1, 2: 0.05},

	## DAMAGE
	# Common items
	SKULL_TROPHY: {0: 0.2, 1: 0.1,},
	SCARAB_AMULET: {0: 0.1, 1: 0.1},
	MAGIC_GLOVES: {0: 0.2, 1: 0.15, 2: 0.05,},
	LAND_MINE: {0: 0.15, 1: 0.15, 2: 0.05, 3: 0.05},
	ORC_WAR_SPEAR: {0: 0.2, 1: 0.15, 2: 0.125, 3: 0.1, 4: 0.05,},
	PIECE_OF_MEAT: {0: 0.25, 1: 0.25, 2: 0.25, 3: 0.2, 4: 0.15, 5: 0.1},
	TOOTH_TROPHY: {0: 0.4, 1: 0.4, 2: 0.4, 3: 0.3, 4: 0.2, 5: 0.1,},
	CLAWS_OF_ATTACK: {0: 0.2, 1: 0.15, 2: 0.125, 3: 0.1, 4: 0.05,},
	HEAVY_CROSSBOW: {0: 0.35, 1: 0.35, 2: 0.35, 3: 0.15, 4: 0.1,},

	# Uncommon items
	BLASTER_STAFF: {0: 0.15, 1: 0.05,},
	
	## TRIGGERS
	# Common items
	RING_OF_LUCK: {0: 0.1, 1: 0.1, 2: 0.01, 3: 0.005},
	ELEGANT_RING: {-1: 0.2, 1: 0.2, 2: 0.2, 3: 0.2, 4: 0.15, 5: 0.1, 6: 0.05,},
	MINI_SHEEP: {-1: 0.2, 1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,},
	ENCHANTED_BIRD_FIGURINE: {-1: 0.8, 6: -0.1, 7: -0.3, 8: -0.55},

	# Uncommon items

	## Attack speed
	# Common items
	ELECTRIFIED_HORSESHOE: {-1: 0.4, 6: -0.25, 7: -0.4, 8: -0.4},

	# Uncommon items


	## Targeted damage mods
	# Common items
	VOID_VIAL: {-1: 0.1, 5: -0.05,6: -0.1, 7: -0.1, 8: -0.1},
	ASSASINATION_ARROW: {0: 0.05, 1: 0.05},
	SPIDER_SILK: {-1: 0.125, 6: -0.075, 7: -0.125, 8: -0.125},
	GARGOYLE_WING: {-1: 0.5, 7: -0.5, 8: -0.5},
	NINJA_GLAIVE: {0: 0.15, 1: 0.15, 2: 0.15, 3: 0.1, 4: 0.1, 5: 0.05,},
	BOMB_SHELLS: {-1: 0.175, 6: -0.1, 7: -0.175, 8: -0.175},
	SHIMMERWEED: {-1: 0.25, 7: -0.1, 8: -0.25},
	RAILGUN: {-1: 0.35, 7: -0.35, 8: -0.35},
	SACRED_HALO: {-1: 0.45, 7: -0.4, 8: -0.45},

	# Uncommon items
	FIERY_ASSASSINATION_ARROW: {0: 0.05, 1: 0.05},

	## MANA
	# Common items
	SCROLL_OF_MYTHS: {-1: 0.1, 1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05, 8: -0.05},
	MAGICAL_ESSENCE: {-1: 0.075, 1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05, 8: -0.05},
	TROLL_VOODOO_MASK: {-1: 0.25, 1: 0.15, 2: 0.15, 3: 0.15, 4: 0.1, 5: 0.1, 6: 0.05, 7: -0.05, 8: -0.1},
	
	# Uncommon items
	TOUCH_OF_A_SPIRIT: {-1: 0.2, 7: -0.05, 8: -0.1},

	## Spell damage
	# Common items
	INSCRIBED_PEBBLE: {-1: 0.25, 6: -0.15, 7: -0.25, 8: -0.25},

	# Uncommon items

	## Exp and gold items
	# Common items
	TRAINING_MANUAL: {0: 0.1, 1: 0.05, 2: 0.05},

	# Uncommon items
	CLAWS_OF_WISDOM: (-1: 0.25, 6: -0.1, 7: -0.25, 8: -0.25),

	SPEED_DEMON_S_REWARD: {0: 0.25, 1: 0.25, 2: 0.25, 3: 0.075},
	


	## Other items
	# Common items
	GIFT_OF_THE_WILD: {-1: 0.1, 5: -0.1, 6: -0.1, 7: -0.1, 8: -0.1},


	STRANGE_ITEM: {-1: 1.0, 8: -1.0},
}

# Optional per-item usage caps: item_id -> (max_count, overflow_usage_value).
# If inventory already has at least max_count copies of the item, the usage
# value of an additional copy is overflow_usage_value (default 0.0 when not
# configured).
USAGE_ITEM_USAGE_CAPS: Dict[ITEM_ID, Tuple[int, GAME_PHASE_VALUE]] = {
	# Example: cap ENCHANTED_MINING_PICK usage after 1 copy, extras worth 0.0.
	#ENCHANTED_MINING_PICK: (1, 0.1),

	# COMMON ITEMS
	RUSTY_MINING_PICK: (1, 0.0),
	YOUNG_THIEF_CLOAK: (1, 0.0),
	OLD_CRYSTAL_BALL: (2, 0.0),
	PIRATE_MAP: (2, 0.0),
	RUNED_WOOD: (2, 0.0),
	MINING_LAMP: (3, 0.0),
	
	SKULL_TROPHY: (2, 0.0),
	SCARAB_AMULET: (1, 0.0),
	MAGIC_GLOVES: (1, 0.0),
	LAND_MINE: (1, 0.0),
	ORC_WAR_SPEAR: (1, 0.0),
	PIECE_OF_MEAT: (2, 0.0),
	TOOTH_TROPHY: (3, 0.0),
	CLAWS_OF_ATTACK: (1, 0.0),

	RING_OF_LUCK: (2, 0.0),
	ELEGANT_RING: (4, 0.0),
	MINI_SHEEP: (2, 0.0),
	ENCHANTED_BIRD_FIGURINE: (6, 0.0),

	ELECTRIFIED_HORSESHOE: (3, 0.0),

	VOID_VIAL: (1, 0.0),
	ASSASINATION_ARROW: (1, 0.0),
	SPIDER_SILK: (1, 0.0),
	GARGOYLE_WING: (1, 0.0),
	NINJA_GLAIVE: (1, 0.0),
	BOMB_SHELLS: (1, 0.0),
	SHIMMERWEED: (1, 0.0),
	RAILGUN: (1, 0.0),
	SACRED_HALO: (1, 0.0),

	SCROLL_OF_MYTHS: (5, 0.0),
	MAGICAL_ESSENCE: (5, 0.0),
	TROLL_VOODOO_MASK: (5, 0.0),

	INSCRIBED_PEBBLE: (2, 0.0),

	GIFT_OF_THE_WILD: (1, 0.0),

	TRAINING_MANUAL: (2, 0.0),

	STRANGE_ITEM: (30, 0.0),

}

# add +1 to all usage_caps
for item_id, (max_count, overflow_value) in USAGE_ITEM_USAGE_CAPS.items():
	USAGE_ITEM_USAGE_CAPS[item_id] = (max_count + 1, overflow_value)

__all__ = [
	"ROOT_DIR",
	"DATA_DIR",
	"ITEM_PROPERTIES_FILE",
	"RECIPE_PROPERTIES_FILE",
	
	"RECIPE_NONE",
	"RECIPE_REBREW",
	"RECIPE_DISTILL",
	"RECIPE_REASSEMBLE",
	"RECIPE_PERFECT",
	"RECIPE_LIQUEFY",
	"RECIPE_PRECIPITATE",
	"RECIPE_IMBUE",

	"ENCHANTED_MINING_PICK",
	"HAUNTED_HAND",
	"STRANGE_ITEM",
]


