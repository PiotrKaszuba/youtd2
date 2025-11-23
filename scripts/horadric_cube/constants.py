from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias, Dict, List, Optional, Tuple, Any

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

# Family ID, Tier, Extra Params
FAMILY_INFO: TypeAlias = Tuple[int, int, Dict[str, Any]]


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

def get_phase_level_bounds(phase: GAME_PHASE) -> Tuple[int, int]:
	"""
	Derive an approximate (lvl_min, lvl_max) range for a given phase index.

	Phases are defined by GAME_PHASES thresholds; the index refers to the
	position in that list.
	"""
	if phase < 0 or phase >= len(GAME_PHASES):
		# Fallback to a wide range if phase index is out of bounds.
		return 0, 1000

	if phase == 0:
		lvl_min = 0
	else:
		prev = GAME_PHASES[phase - 1]
		lvl_min = 0 if not np.isfinite(prev) else int(prev) + 1

	current = GAME_PHASES[phase]
	lvl_max = 1000 if not np.isfinite(current) else int(current)

	return lvl_min, lvl_max


def get_phase_avg_level(phase: GAME_PHASE) -> int:
	"""
	Get the average level for a given phase index.
	"""
	lvl_min, lvl_max = get_phase_level_bounds(phase)
	return (lvl_min + lvl_max) // 2


@dataclass(frozen=True)
class FamilyRule:
	downward_impacts: Dict[int, GAME_PHASE_VALUE_DICT] = field(default_factory=dict)

# Map family_id -> FamilyRule
FAMILY_RULES: Dict[int, FamilyRule] = {}

@dataclass(frozen=True)
class ItemValue:
	item_id: ITEM_ID
	usage_value: GAME_PHASE_VALUE_DICT
	transmute_value: GAME_PHASE_VALUE_DICT  # learned later
	# Optional: hold all strategy tables for inspection (keyed by strategy name).
	# If provided, the "transmute_value" is the selected output strategy face value.
	transmute_values_by_strategy: Optional[Dict[str, GAME_PHASE_VALUE_DICT]] = None
	usage_cap: Optional[Tuple[int, GAME_PHASE_VALUE]] = None
	family_info: Optional[FAMILY_INFO] = None

	def update_keep_transmute_value(
		self,
		usage_value: GAME_PHASE_VALUE_DICT,
		inventory: Optional[Inventory] = None,
		usage_caps: Optional[Dict[ITEM_ID, Tuple[int, GAME_PHASE_VALUE]]] = None,
		usage_cap_single: Optional[Tuple[int, GAME_PHASE_VALUE]] = None,
		family_info: Optional[FAMILY_INFO] = None,
	) -> ItemValue:
		"""
		Update the ItemValue with new usage value and caps, keeping the transmute value.
		"""
		if family_info is None:
			family_info = self.family_info

		usage_value_full = ItemValue.determine_usage_value(
			self.item_id, usage_value, usage_caps, usage_cap_single, inventory, family_info
		)
		final_cap = ItemValue.determine_cap(self.item_id, usage_caps, usage_cap_single)
		return ItemValue(
			item_id=self.item_id,
			usage_value=usage_value_full,
			transmute_value=self.transmute_value,
			transmute_values_by_strategy=self.transmute_values_by_strategy,
			usage_cap=final_cap,
			family_info=family_info
		)


	@staticmethod
	def determine_cap(
		item_id: ITEM_ID,
		usage_caps: Optional[Dict[ITEM_ID, Tuple[int, GAME_PHASE_VALUE]]] = None,
		usage_cap_single: Optional[Tuple[int, GAME_PHASE_VALUE]] = None,
	) -> Tuple[int, GAME_PHASE_VALUE]:
		"""
		Determine the final cap for a given item ID.
		"""
		# Resolve cap from direct argument or dict lookup
		if usage_cap_single is None and usage_caps is not None:
			return usage_caps.get(item_id)
		return usage_cap_single

	@staticmethod
	def determine_usage_value(
		item_id: ITEM_ID,
		usage_value: GAME_PHASE_VALUE_DICT,
		usage_caps: Optional[Dict[ITEM_ID, Tuple[int, GAME_PHASE_VALUE]]] = None,
		usage_cap_single: Optional[Tuple[int, GAME_PHASE_VALUE]] = None,
		inventory: Optional[Inventory] = None,
		family_info: Optional[FAMILY_INFO] = None,
	) -> GAME_PHASE_VALUE_DICT:
		"""
		Determine the final usage value for a given item ID.
		"""
		if usage_value is None:
			usage_value = {phase: 0.0 for phase in range(len(GAME_PHASES))}
		else:
			usage_value = usage_value.copy()
		
		base_usage_value = usage_value.pop(-1, 0.0)
		usage_value_full = {phase: base_usage_value + usage_value.get(phase, 0.0) for phase in range(len(GAME_PHASES))}
		
		final_cap = ItemValue.determine_cap(item_id, usage_caps, usage_cap_single)

		# Apply inventory-aware caps if requested.
		if inventory is not None and final_cap is not None:
			count = inventory.get(item_id, 0)
			max_count, overflow_val = final_cap
			
			# Check for family shadowing if applicable
			shadow_count_by_phase = {p: 0.0 for p in range(len(GAME_PHASES))}
			if family_info:
				fam_id, tier, _ = family_info
				# We need to scan inventory for higher tier items of same family
				for other_id, other_count in inventory.items():
					if other_count <= 0:
						continue
					other_fam_info = get_item_family_info(other_id)
					if not other_fam_info:
						continue
					other_fam_id, other_tier, _ = other_fam_info
					
					if other_fam_id == fam_id and other_tier > tier:
						tier_diff = other_tier - tier
						rule = FAMILY_RULES.get(fam_id)
						if rule and tier_diff in rule.downward_impacts:
							impact_dict = rule.downward_impacts[tier_diff]
							base_impact = impact_dict.get(-1, 0.0)
							for p in range(len(GAME_PHASES)):
								impact = base_impact + impact_dict.get(p, 0.0)
								shadow_count_by_phase[p] += other_count * impact

			for phase_idx in range(len(GAME_PHASES)):
				effective_count = count + shadow_count_by_phase[phase_idx]
				if max_count is not None and effective_count >= max_count:
					usage_value_full[phase_idx] = overflow_val

		return usage_value_full

	@staticmethod
	def from_data(
		item_id: ITEM_ID,
		usage_value: GAME_PHASE_VALUE_DICT = None,
		inventory: Optional[Inventory] = None,
		usage_caps: Optional[Dict[ITEM_ID, Tuple[int, GAME_PHASE_VALUE]]] = None,
		usage_cap_single: Optional[Tuple[int, GAME_PHASE_VALUE]] = None,
		family_info: Optional[FAMILY_INFO] = None,
	) -> ItemValue:
		"""
		Build an ItemValue from sparse usage_value data.

		- usage_value may contain a base value at key -1 and optional per-phase
		  overrides keyed by phase index.
		- If inventory and usage_caps are provided and the inventory already
		  contains at least max_count copies of this item, usage values are
		  collapsed to the configured overflow value (default 0.0 when not set).
		"""
		usage_value_full = ItemValue.determine_usage_value(item_id, usage_value, usage_caps, usage_cap_single, inventory, family_info)
		final_cap = ItemValue.determine_cap(item_id, usage_caps, usage_cap_single)
		transmute_value_full = {phase_idx: 0.0 for phase_idx in range(len(GAME_PHASES))}
		return ItemValue(item_id, usage_value_full, transmute_value_full, None, final_cap, family_info)


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
# These include ENCHANTED_MINING_PICK, HAUNTED_HAND, CHRONO_JUMPER, and WORKBENCH,
# which are defined in the rarity sections below.

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


# RARE ITEMS

ENCHANTED_MINING_PICK: int = 8
CURSED_CLAW: int = 10
FIST_OF_DOOM: int = 14
DIVINE_SHIELD: int = 22
LOVE_POTION: int = 23
PHOENIX_EGG: int = 32
LUCKY_DICE: int = 48
SCEPTER_OF_THE_LUNAR_LIGHT: int = 49
MAGIC_HAMMER: int = 50
SILVER_ARMOR: int = 59
CLAWS_OF_URSUS: int = 76
THUNDER_GLOVES: int = 101
SPIDERLING: int = 105
PURIFYING_GLOVES: int = 120
MEDALLION_OF_OPULENCE: int = 122
FORCEFIELD_GENERATOR: int = 126
CRESCENT_STONE: int = 127
HIPPOGRYPH_EGG: int = 130
MANA_STONE: int = 131
THE_SUCONA: int = 133
BARTUC_S_SPIRIT: int = 138
TOY_BOY: int = 146
WRITER_S_KNOWLEDGE: int = 152
ELITE_SHARP_SHOOTER: int = 154
SIGN_OF_ENERGY_INFUSION: int = 156
COMMANDER: int = 161
BASICS_OF_CALCULUS: int = 165
WAND_OF_MANA_ZAP: int = 166
NEVER_ENDING_KEG: int = 167
ETERNIUM_BLADE: int = 171
ESSENCE_OF_ROT: int = 174
RITUAL_TALISMAN: int = 179
LIBRAM_OF_GRACE: int = 180
BLOODTHIRSTY_WHEEL_OF_FORTUNE: int = 181
LIQUID_GOLD: int = 186
STAFF_OF_THE_WILD_EQUUS: int = 188
MAGNETIC_FIELD: int = 197
OPTIMIST_S_PRESERVED_FACE: int = 202
SWORD_OF_RECKONING: int = 203
SWORD_OF_DECAY: int = 205
MINDLEECHER: int = 206
SHINING_ROCK: int = 212
LICH_MASK: int = 213
BRIMSTONE_HELMET: int = 214
SHARE_KNOWLEDGE: int = 217
BOOK_OF_KNOWLEDGE: int = 222
BLOODY_KEY: int = 228
CURRENCY_CONVERTER: int = 231
ENCHANTED_GEAR: int = 237
SECRET_TOME_OF_MAGIC: int = 238
SECRET_TOME_OF_MANA: int = 239
OLD_HUNTER: int = 242
ARMS_DEALER: int = 244
HAUNTED_HAND: int = 246
CHAMELEONS_SOUL: int = 247
ARCANE_SCRIPT: int = 251
BALL_LIGHTNING: int = 255
SPEAR_OF_THE_MALPHAI: int = 258
CRYSTALLINE_ARROW: int = 260
GRANITE_HAMMER: int = 262
STUNNER: int = 269
EL_BASTARDO: int = 270
SCROLL_OF_STRENGTH: int = 272
SCROLL_OF_SPEED: int = 273
PHASE_GLOVES: int = 276
AMULET_OF_STRENGTH: int = 278
SHACKLES_OF_TIME: int = 283
DIVINE_OIL_OF_SHARPNESS: int = 1003
DIVINE_OIL_OF_MAGIC: int = 1006
DIVINE_OIL_OF_ACCURACY: int = 1009
DIVINE_OIL_OF_SWIFTNESS: int = 1012
DIVINE_OIL_OF_SORCERY: int = 1015
ARCANE_OIL_OF_EXUBERANCE: int = 1017
SEEKER_S_ARCANE_OIL: int = 1019
ARCANE_OIL_OF_LORE: int = 1021
MINE_CART: int = 2004
CONSUMABLE_PIGGY: int = 2005
DIVINE_BOOK_OF_OMNIPOTENCE: int = 2007


# UNIQUE ITEMS

ARTIFACT_OF_SKADI: int = 1
BACKPACK: int = 9
STASIS_TRAP: int = 13
CRUEL_TORCH: int = 17
ENCHANTED_KNIVES: int = 18
BONK_S_FACE: int = 35
SLEEVE_OF_RAGE: int = 42
EXCALIBUR: int = 45
BHAAL_S_ESSENCE: int = 56
WAR_DRUM: int = 58
FLAG_OF_THE_ALLEGIANCE: int = 60
GOLDEN_DECORATION: int = 61
JEWELS_OF_THE_MOON: int = 62
PRIEST_FIGURINE: int = 103
DAGGER_OF_BANE: int = 132
PENDANT_OF_PROMPTNESS: int = 137
CHRONO_JUMPER: int = 140
JAH_RAKAL_S_FURY: int = 142
JUNGLE_STALKER_S_DOLL: int = 149
GLAIVE_OF_SUPREME_FOLLOW_UP: int = 162
DARK_MATTER_TRIDENT: int = 178
MIGHTY_TREE_S_ACORNS: int = 183
SOUL_COLLECTORS_CLOAK: int = 184
STAFF_OF_ESSENCE: int = 193
FROG_PIPE: int = 198
SPELLBOOK_OF_ITEM_MASTERY: int = 200
EVEN_MORE_MAGICAL_HAMMER: int = 201
M_E_F_I_S_ROCKET: int = 207
FRAGMENTATION_ROUND: int = 208
GROUNDING_GLOVES: int = 209
OVERCHARGE_SHOT: int = 215
PENDANT_OF_MANA_SUPREMACY: int = 216
LUNAR_ESSENCE: int = 227
THE_DIVINE_WINGS_OF_TRAGEDY: int = 230
MINI_FOREST_TROLL: int = 240
HOLY_HAND_GRENADE: int = 241
CIRCLE_OF_POWER: int = 245
POCKET_EMPORIUM: int = 248
GOLDEN_TRIDENT: int = 249
CRIT_BLADE: int = 250
SOUL_COLLECTOR_S_SCYTHE: int = 252
DOOM_S_ENSIGN: int = 253
DISTORTED_IDOL: int = 254
VAMPIRIC_SKULL: int = 261
SPEAR_OF_LOKI: int = 264
ELUNES_BOW: int = 266
ELUNES_QUIVER: int = 267
SOUL_EXTRACTOR: int = 268
PORTABLE_TOMBSTONE: int = 274
WORKBENCH: int = 275
MAGIC_CONDUCTOR: int = 279
FAITHFUL_STAFF: int = 281
LUCKY_GEM: int = 282
CHAMELEON_GLAIVE: int = 284
HELM_OF_INSANITY: int = 285
TEARS_OF_THE_GODS: int = 1022
PURE_AETHER: int = 1023
WIZARD_S_SOUL: int = 1024
CONSUMABLE_HOBBIT: int = 2008


# -1 is a special GAME_PHASE to be used as base value for all game phases

# Tuple[int, GAME_PHASE_VALUE]:
# Optional per-item usage caps: item_id -> (max_count, overflow_usage_value).
# If inventory already has at least max_count copies of the item, the usage
# value of an additional copy is overflow_usage_value (default 0.0 when not
# configured).

USAGE_ITEM_VALUES: Dict[ITEM_ID, Tuple[GAME_PHASE_VALUE_DICT, Optional[Tuple[int, GAME_PHASE_VALUE]], Optional[FAMILY_INFO]]] = {
	# ENCHANTED_MINING_PICK: {-1: 1.0}

	## ITEM FIND  / QUALITY
	# Common items
	RUSTY_MINING_PICK: ({0: 0.1, 1: 0.1, 2: 0.05}, (1, 0.0), None),
	YOUNG_THIEF_CLOAK: ({0: 0.25, 1: 0.25, 2: 0.25, 3: 0.1,}, (2, 0.0), None),
	OLD_CRYSTAL_BALL: ({0: 0.25, 1: 0.25, 2: 0.25, 3: 0.1,}, (2, 0.0), None),
	PIRATE_MAP: ({0: 0.55, 1: 0.55, 2: 0.375, 3: 0.275, 4: 0.125, 5: 0.075,}, (2, 0.0), None),
	RUNED_WOOD: ({-1: 0.35, 4: -0.1, 5: -0.15, 6: -0.25, 7: -0.35, 8: -0.35}, (2, 0.0), None),
	MINING_LAMP: ({-1: 1.35, 6: -0.35, 7: -0.85, 8: -1.35}, (3, 0.0), None),

	# Uncommon items
	TINY_RABBIT: ({0: 0.1, 1: 0.1, 2: 0.05}, (1, 0.0), None),
	HUNTING_MAP: ({0: 0.25, 1: 0.25, 2: 0.25, 3: 0.1,}, (2, 0.0), None),
	DOWSING_ROD: ({-1: 0.95, 6: -0.275, 7: -0.775, 8: -0.95}, (3, 0.0), None),
	SUPPORT_COLUMN: ({0: 0.375, 1: 0.375, 2: 0.375, 3: 0.325, 4: 0.175, 5: 0.075, }, (3, 0.0), None),
	DUMPSTER: ({-1: 0.575, 6: -0.225, 7: -0.525, 8: -0.575}, (2, 0.0), None),
	SURVIVAL_KIT: ({0: 0.4, 1: 0.4, 2: 0.375, 3: 0.275, 4: 0.125, 5: 0.05}, (3, 0.0), None),
	ENCHANTED_TELESCOPE: ({-1: 0.7, 5: -0.2, 6: -0.45, 7: -0.7, 8: -0.7}, (2, 0.0), None),
	MASTER_THIEF_S_SHROUD: ({-1: 1.0, 6: -0.25, 7: -0.75, 8: -1.0}, (2, 0.0), None),
	MONOCLE: ({-1: 2.25, 6: -0.25, 7: -0.75, 8: -2.25}, (3, 0.0), None),
	GRAND_SEAL_OF_PICKINESS: ({-1: 2.75, 6: -0.25, 7: -0.75, 8: -2.75}, (2, 0.0), None),
	SPIDER_BROACH: ({-1: 3.0, 6: -0.25, 7: -0.75, 8: -3.0}, (2, 0.0), None),
	SHADOWFOOT_S_MANTLE: ({-1: 2.25, 6: -0.25, 7: -0.75, 8: -2.25}, (2, 0.0), None),

	# Rare items
	BLOODTHIRSTY_WHEEL_OF_FORTUNE: ({-1: 1.9, 6: -0.25, 7: -0.7, 8: -2.25}, (2, 0.0), None),
	ENCHANTED_MINING_PICK: ({-1: 2.45, 6: -0.25, 7: -0.75, 8: -2.45}, (2, 0.0), None),

	# Unique items
	BACKPACK: ({0: 1.0, 1: 1.0, 2: 1.0, 3: 0.75, 4: 0.5, 5: 0.5, 6: 0.25}, (2, 0.0), None),
	WORKBENCH: ({0: 3.5, 1: 3.4, 2: 3.25, 3: 3.05, 4: 2.8, 5: 2.5, 6: 2.25, 7: 0.5, 8: 0.0}, (2, 0.0), None),
	POCKET_EMPORIUM: ({0: 2.5, 1: 2.5, 2: 2.5, 3: 2.25, 4: 2.0, 5: 1.75, 6: 1.35, 7: 0.5, 8: 0}, (5, 0.0), None),
	SPELLBOOK_OF_ITEM_MASTERY: ({0: 4.0, 1: 4.0, 2: 3.75, 4: 3.4, 5: 3., 6: 2.5, 7: 0.9, 8: 0.0}, (3, 0.0), None),

	## DAMAGE
	# Common items
	SKULL_TROPHY: ({0: 0.2, 1: 0.1,}, (2, 0.0), None),
	SCARAB_AMULET: ({0: 0.1, 1: 0.1}, (1, 0.0), None),
	MAGIC_GLOVES: ({0: 0.275, 1: 0.2, 2: 0.1,}, (1, 0.0), None),
	LAND_MINE: ({0: 0.15, 1: 0.15, 2: 0.05, 3: 0.05}, (1, 0.0), None),
	ORC_WAR_SPEAR: ({0: 0.2, 1: 0.15, 2: 0.125, 3: 0.1, 4: 0.05,}, (1, 0.0), None),
	PIECE_OF_MEAT: ({0: 0.25, 1: 0.25, 2: 0.25, 3: 0.2, 4: 0.15, 5: 0.1}, (2, 0.0), None),
	TOOTH_TROPHY: ({0: 0.4, 1: 0.4, 2: 0.35, 3: 0.25, 4: 0.125, 5: 0.05,}, (3, 0.0), None),
	CLAWS_OF_ATTACK: ({0: 0.2, 1: 0.15, 2: 0.125, 3: 0.1, 4: 0.05,}, (1, 0.0), None),
	HEAVY_CROSSBOW: ({0: 0.35, 1: 0.35, 2: 0.35, 3: 0.15, 4: 0.1,}, (1, 0.0), None),

	# Uncommon items
	BLASTER_STAFF: ({0: 0.15, 1: 0.05,}, (2, 0.0), None),
	UNYIELDING_MAUL: ({0: 0.15, 1: 0.1, 2: 0.075, 3: 0.05,}, (1, 0.0), None),
	RAZOR_SHARP_DAGGER: ({-1: 0.1, 5: -0.05, 6: -0.1, 7: -0.1, 8: -0.1}, (1, 0.0), None),
	BLOODTHIRSTY_AXE: ({-1: 0.1, 5: -0.05, 6: -0.1, 7: -0.1, 8: -0.1}, (1, 0.0), None),
	CLAWS_OF_THE_BEAR: ({0: 0.1, 1: 0.1, 2: 0.05}, (1, 0.0), None),
	WINE_OF_ALUQAH: ({0: 0.3, 1: 0.3, 2: 0.175, 3: 0.15, 4: 0.1, 5: 0.05}, (2, 0.0), None),
	ZOMBIE_HEAD: ({-1: 0.65}, (3, 0.0), None),
	BATTLE_SUIT: ({0: 0.35, 1: 0.35, 2: 0.35, 3: 0.2, 4: 0.125, 5: 0.05}, (2, 0.0), None),
	HEAVY_GUN: ({-1: 0.65, 6: -0.2, 7: -0.4, 8: -0.6}, (3, 0.0), None),
	POLARISATOR: ({-1: 0.2, 6: -0.1, 7: -0.2, 8: -0.2}, (1, 0.0), None),
	DRAGON_CLAWS: ({-1: 0.2, 6: -0.125, 7: -0.2, 8: -0.2}, (1, 0.0), None),
	DRAGON_S_HEART: ({-1: 0.3, 6: -0.1, 7: -0.25, 8: -0.25}, (1, 0.0), None),
	NAGA_TRIDENT: ({-1: 0.4, 6: -0.1, 7: -0.225, 8: -0.25}, (2, 0.0), None),
	
	MINI_TANK: ({-1: 0.8, 6: -0.2, 7: -0.4, 8: -0.75}, (2, 0.0), None),
	BEAST_HEAD: ({-1: 0.8, 6: -0.2, 7: -0.4, 8: -0.75}, (2, 0.0), None),

	# Rare items
	PURIFYING_GLOVES: ({-1: 0.05, 0: 0.2, 1: 0.15, 2: 0.1,}, (2, 0.0), None),
	LIQUID_GOLD: ({0: 0.2, 1: 0.15, 2: 0.125, 3: 0.1, 4: 0.05}, (1, 0.0), None),
	FIST_OF_DOOM: ({-1: 0.4, 5: -0.1, 6: -0.2, 7: -0.35, 8: -0.4}, (1, 0.0), None),
	HIPPOGRYPH_EGG: ({0: 0.4, 1: 0.4, 2: 0.4, 3: 0.3, 4: 0.25, 5: 0.1,}, (1, 0.0), None),

	SIGN_OF_ENERGY_INFUSION: ({-1: 0.4}, (3, 0.0), None),
	OPTIMIST_S_PRESERVED_FACE: ({-1: 0.4, 6: -0.15, 7: -0.25, 8: -0.3}, (1, 0.0), None),
	GRANITE_HAMMER: ({-1: 0.2, 6: -0.1, 7: -0.2, 8: -0.2}, (1, 0.0), None),
	BARTUC_S_SPIRIT: ({0: 0.45, 1: 0.45, 2: 0.45, 3: 0.325, 4: 0.25, 5: 0.1}, (1, 0.0), None),
	CLAWS_OF_URSUS: ({0: 0.3, 1: 0.3, 2: 0.25, 3: 0.2, 4: 0.15, 5: 0.1,}, (1, 0.0), None),
	NEVER_ENDING_KEG: ({-1: 0.25, 6: -0.15, 7: -0.25, 8: -0.25}, (1, 0.0), None),
	SILVER_ARMOR: ({-1: 0.05, 6: -0.05, 7: -0.05, 8: -0.05}, (1, 0.0), None),
	ELITE_SHARP_SHOOTER: ({-1: 0.5, 7: -0.1, 8: -0.2}, (1, 0.0), None),
	SPEAR_OF_THE_MALPHAI: ({-1: 0.5, 7: -0.1, 8: -0.2}, (1, 0.0), None),
	LUCKY_DICE: ({-1: 0.55, 7: -0.1, 8: -0.25,}, (2, 0.0), None),
	TOY_BOY: ({-1: 0.5, 6: -0.15, 7: -0.35, 8: -0.475}, (1, 0.0), None),
	AMULET_OF_STRENGTH: ({-1: 0.9, 6: -0.2, 7: -0.4, 8: -0.8}, (1, 0.0), None),
	ETERNIUM_BLADE: ({-1: 1.75, 7: -0.25, 8: -0.75}, (2, 0.0), None),

	# Unique items
	HELM_OF_INSANITY: ({-1: 0.6, 6: -0.25, 7: -0.6, 8: -0.6}, (1, 0.0), None),
	JUNGLE_STALKER_S_DOLL: ({-1: 0.15, 5: -0.05, 6: -0.1, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	CRIT_BLADE: ({-1: 0.475, 6: -0.2, 7: -0.325, 8: - 0.375}, (1, 0.0), None),
	DAGGER_OF_BANE: ({-1: 2.25, 7: -0.7, 8: -1.6}, (1, 0.0), None),
	BONK_S_FACE: ({-1: 1.75, 7: -0.6, 8: -1.3}, (1, 0.0), None),
	OVERCHARGE_SHOT: ({-1: 3.25, }, (1, 0.0), None),
	MINI_FOREST_TROLL: ({-1: 0.85, 7: -0.1, 8: -0.3}, (1, 0.0), None),
	ELUNES_BOW: ({-1: 0.75, 6: -0.25, 7: -0.4, 8: -0.55}, (1, 0.0), None),
	SOUL_COLLECTOR_S_SCYTHE: ({-1: 2.25, 7: -0.5, 8: -2.25}, (2, 0.0), None),
	SOUL_COLLECTORS_CLOAK: ({-1: 2.25, 7: -0.5, 8: -2.25}, (2, 0.0), None),
	CHAMELEON_GLAIVE: ({-1: 2.75, 7: -0.25, 8: -0.5}, (1, 0.0), None),
	SPEAR_OF_LOKI: ({-1: 0.4, 6: -0.2, 7: -0.4, 8: -0.4}, (1, 0.0), None),
	GROUNDING_GLOVES: ({-1: 0.65, 4: -0.05, 5: -0.1, 6: -0.15, 7: -0.25, 8: -0.25}, (2, 0.0), None),
	FROG_PIPE: ({-1: 3.25}, (1, 0.0), None),
	FRAGMENTATION_ROUND: ({-1: 4.5}, (1, 0.0), None),
	SLEEVE_OF_RAGE: ({-1: 1.4}, (1, 0.0), None),
	GLAIVE_OF_SUPREME_FOLLOW_UP: ({-1: 2.5, 7: -0.75, 8: -1.5}, (1, 0.0), None),
	STAFF_OF_ESSENCE: ({-1: 1.0}, (1, 0.0), None),
	HOLY_HAND_GRENADE: ({-1: 4.5}, (1, 0.0), None),
	ENCHANTED_KNIVES: ({-1: 5.0}, (4, 0.0), None),


	## BUFFS

	# Uncommon items
	TOME_OF_SHADOW_MAGIC: ({-1: 0.2, 5: -0.05, 6: -0.1, 7: -0.125, 8: -0.175}, (5, 0.0), None),
	MAGIC_VIAL: ({-1: 0.25, 5: -0.025, 6: -0.075, 7: -0.125, 8: -0.25}, (5, 0.0), None),
	HERMIT_STAFF: ({-1: 0.575, 6: -0.075, 7: -0.125, 8: -0.35}, (4, 0.0), None),
	ZOMBIE_HAND: ({-1: 0.875, 6: -0.125, 7: -0.2, 8: -0.55}, (4, 0.0), None),
	TROLL_CHARM: ({-1: 0.5, 6: -0.1, 7: -0.15, 8: -0.35}, (5, 0.0), None),
	PANDA_DRESS: ({-1: 2.0, 7: -0.25, 8: -0.5}, (4, 0.0), None),

	# Rare items
	LOVE_POTION: ({-1: 1.85, 7: -0.25, 8: -0.5}, (4, 0.0), None),
	PHOENIX_EGG: ({-1: 0.5, 6: -0.1, 7: -0.15, 8: -0.35}, (5, 0.0), None),
	
	
	## TRIGGERS
	# Common items
	RING_OF_LUCK: ({0: 0.1, 1: 0.1, 2: 0.1, 3: 0.05}, (2, 0.0), None),
	ELEGANT_RING: ({0: 0.375, 1: 0.375, 2: 0.375, 3: 0.35, 4: 0.225, 5: 0.2, 6: 0.05,}, (4, 0.0), None),
	MINI_SHEEP: ({0: 0.175, 1: 0.175, 2: 0.175, 3: 0.15, 4: 0.1, 5: 0.05,}, (2, 0.0), None),
	ENCHANTED_BIRD_FIGURINE: ({-1: 0.8, 6: -0.1, 7: -0.3, 8: -0.55}, (4, 0.0), None),

	# Uncommon items
	SHINY_EMERALD: ({-1: 0.5, 6: -0.1, 7: -0.25, 8: -0.425}, (5, 0.0), None),
	RING_OF_CHANCE: ({-1: 0.35, 5: -0.075, 6: -0.125, 7: -0.225, 8: -0.325}, (4, 0.0), None),
	ARCHER_S_HOOD: ({-1: 0.425, 5: -0.075, 6: -0.15, 7: -0.3, 8: -0.4}, (3, 0.0), None),
	MINDS_KEY: ({-1: 0.5, 6: -0.1, 7: -0.25, 8: -0.425}, (5, 0.0), None),

	# Rare items
	CRESCENT_STONE: ({-1: 0.25, 5: -0.05, 6: -0.1, 7: -0.2, 8: -0.225}, (2, 0.0), None),
	SHACKLES_OF_TIME: ({-1: 0.95, 7: -0.1, 8: -0.35}, (4, 0.0), None),


	## Attack speed
	# Common items
	ELECTRIFIED_HORSESHOE: ({-1: 0.325, 6: -0.225, 7: -0.325, 8: -0.325}, (3, 0.0), None),

	# Uncommon items
	QUICKTRIGGER_BLADE: ({-1: 0.1, 5: -0.05, 6: -0.1, 7: -0.1, 8: -0.1}, (2, 0.0), None),
	GLOWING_GAUNTLETS: ({-1: 0.1, 5: -0.05, 6: -0.1, 7: -0.1, 8: -0.1}, (2, 0.0), None),
	LIGHTNING_BOOTS: ({-1: 0.5, 6: -0.1, 7: -0.2, 8: -0.25}, (4, 0.0), None),
	FLAMING_ARROW: ({-1: 0.25, 6: -0.2, 7: -0.25, 8: -0.25}, (2, 0.0), None),
	VULSHOK_S_CLAWS: ({-1: 0.35, 6: -0.2, 7: -0.325, 8: -0.35}, (2, 0.0), None),
	
	# Rare items
	BALL_LIGHTNING: ({-1: 0.1, 6: -0.05, 7: -0.1, 8: -0.1}, (1, 0.0), None),
	ENCHANTED_GEAR: ({-1: 0.5, 6: -0.1, 7: -0.25, 8: -0.425}, (3, 0.0), None),

	# Unique items
	DARK_MATTER_TRIDENT: ({-1: 0.5, 6: -0.1, 7: -0.2, 8: -0.25}, (4, 0.0), None),
	JAH_RAKAL_S_FURY: ({-1: 0.15, 5: -0.05, 6: -0.1, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	ELUNES_QUIVER: ({-1: 0.95, 7: -0.15, 8: -0.2}, (4, 0.0), None),
	PENDANT_OF_PROMPTNESS: ({-1: 0.25}, (1, 0.0), None),


	

	

	## Targeted damage mods
	# Common items
	VOID_VIAL: ({-1: 0.1, 4: -0.05, 5: -0.1, 6: -0.1, 7: -0.1, 8: -0.1}, (1, 0.0), None),
	ASSASINATION_ARROW: ({0: 0.05, 1: 0.05}, (1, 0.0), None),
	SPIDER_SILK: ({-1: 0.15, 6: -0.1, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	GARGOYLE_WING: ({-1: 0.5, 7: -0.4, 8: -0.4}, (1, 0.0), None),
	NINJA_GLAIVE: ({0: 0.15, 1: 0.15, 2: 0.15, 3: 0.1, 4: 0.1, 5: 0.05,}, (1, 0.0), None),
	BOMB_SHELLS: ({-1: 0.25, 6: -0.125, 7: -0.225, 8: -0.225}, (1, 0.0), None),
	SHIMMERWEED: ({-1: 0.25, 6: -0.125, 7: -0.175, 8: -0.25}, (1, 0.0), None),
	RAILGUN: ({-1: 0.35, 6: -0.25, 7: -0.35, 8: -0.35}, (1, 0.0), None),
	SACRED_HALO: ({-1: 0.45, 6: -0.2, 7: -0.4, 8: -0.45}, (1, 0.0), None),

	# Uncommon items
	FIERY_ASSASSINATION_ARROW: ({0: 0.05, 1: 0.05}, (1, 0.0), None),
	SCROLL_OF_PIERCING_MAGIC: ({-1: 0.2, 5: -0.05, 6: -0.1, 7: -0.2, 8: -0.2}, (1, 0.0), None),
	AQUEOUS_VAPOR: ({-1: 0.15, 5: -0.1, 6: -0.15, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	DEEP_SHADOWS: ({-1: 0.15, 5: -0.1, 6: -0.15, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	UNSTABLE_CURRENT: ({-1: 0.15, 5: -0.1, 6: -0.15, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	SHRAPNEL_AMMUNITION: ({-1: 0.15, 5: -0.1, 6: -0.15, 7: -0.15, 8: -0.15}, (1, 0.0), None),

	HAND_OF_RUIN: ({0: 0.1, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.05,}, (1, 0.0), None),
	AXE_OF_DECAPITATION: ({-1: 0.35, 6: -0.2, 7: -0.3, 8: -0.35}, (1, 0.0), None),
	TOXIC_CHEMICALS: ({-1: 0.225, 5: -0.125, 6: -0.15, 7: -0.225, 8: -0.225}, (1, 0.0), None),

	BONES_OF_ESSENCE: ({-1: 0.15, 5: -0.1, 6: -0.15, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	COMBAT_GLOVES: ({-1: 0.4, 6: -0.15, 7: -0.35, 8: -0.4}, (1, 0.0), None),
	MASK_OF_SANITY: ({-1: 0.475, 6: -0.175, 7: -0.375, 8: -0.425}, (1, 0.0), None),

	OGRE_BATTLE_AXE: ({-1: 0.35, 6: -0.3, 7: -0.35, 8: -0.35}, (1, 0.0), None),
	CRYSTAL_STAFF: ({-1: 0.375, 6: -0.3, 7: -0.375, 8: -0.375}, (1, 0.0), None),

	# Rare items
	BRIMSTONE_HELMET: ({-1: 0.15, 5: -0.1, 6: -0.15, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	LICH_MASK: ({-1: 0.15, 5: -0.1, 6: -0.15, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	PHASE_GLOVES: ({-1: 0.4, 7: -0.15, 8: -0.3}, (1, 0.0), None),

	EL_BASTARDO: ({-1: 0.85, 6: -0.15, 7: -0.25, 8: -0.35}, (1, 0.0), None),
	SCEPTER_OF_THE_LUNAR_LIGHT: ({-1: 0.35, 6: -0.25, 7: -0.3, 8: -0.325}, (1, 0.0), None),
	THE_SUCONA: ({-1: 0.5}, (1, 0.0), None),


	## MANA
	# Common items
	SCROLL_OF_MYTHS: ({-1: 0.1, 1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05, 8: -0.05}, (5, 0.0), None),
	MAGICAL_ESSENCE: ({-1: 0.075, 1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05, 8: -0.05}, (5, 0.0), None),
	TROLL_VOODOO_MASK: ({-1: 0.25, 1: 0.15, 2: 0.15, 3: 0.15, 4: 0.1, 5: 0.1, 6: 0.05, 7: -0.05, 8: -0.1}, (5, 0.0), None),
	
	# Uncommon items
	TOUCH_OF_A_SPIRIT: ({-1: 0.2, 7: -0.05, 8: -0.1}, (5, 0.0), None),
	WIZARD_STAFF: ({-1: 0.25, 6: -0.1, 7: -0.2, 8: -0.225}, (1, 0.0), None),
	ANCIENT_FIGURINE: ({-1: 0.4, 7: -0.15, 8: -0.2}, (5, 0.0), None),
	SAGE_S_MASK: ({-1: 0.55, 7: -0.1, 8: -0.15}, (5, 0.0), None),

	# Rare items
	MANA_STONE: ({-1: 0.15, 7: -0.05, 8: -0.1}, (2, 0.0), None),
	SECRET_TOME_OF_MANA: ({-1: 0.35}, (1, 0.0), None),

	# Unique items
	VAMPIRIC_SKULL: ({-1: 1.0}, (1, 0.0), None),
	CIRCLE_OF_POWER: ({-1: 1.0}, (2, 0.0), None),
	PENDANT_OF_MANA_SUPREMACY: ({-1: 0.9, }, (5, 0.0), None),

	## Spell damage
	# Common items
	INSCRIBED_PEBBLE: ({-1: 0.25, 6: -0.15, 7: -0.25, 8: -0.25}, (2, 0.0), None),

	# Uncommon items
	MAGIC_FLOWER: ({-1: 0.15, 4: -0.05, 5: -0.1, 6: -0.15, 7: -0.15, 8: -0.15}, (2, 0.0), None),
	CEREMONIAL_SKULL: ({-1: 0.25, 5: -0.05, 6: -0.15, 7: -0.225, 8: -0.225}, (2, 0.0), None),
	SPARKLING_STAFF: ({-1: 0.15, 4: -0.05, 5: -0.1, 6: -0.15, 7: -0.15, 8: -0.15}, (2, 0.0), None),
	DEMONIC_ORB: ({-1: 0.1, 5: -0.05, 6: -0.05, 7: -0.1, 8: -0.1}, (1, 0.0), None),
	MAGICIAN_S_DOORKEY: ({-1: 0.1, 5: -0.05, 6: -0.1, 7: -0.1, 8: -0.1}, (1, 0.0), None),
	ARCANE_EYE: ({-1: 0.25, 5: -0.05, 6: -0.15, 7: -0.225, 8: -0.225}, (2, 0.0), None),
	MOONSILVER_CIRCLET: ({-1: 0.4, 7: -0.15, 8: -0.25}, (2, 0.0), None),

	# Rare items
	MAGIC_HAMMER: ({-1: 0.15, 6: -0.1, 7: -0.15, 8: -0.15}, (1, 0.0), None),
	SECRET_TOME_OF_MAGIC: ({-1: 0.4}, (1, 0.0), None),
	THUNDER_GLOVES: ({-1: 0.4, 6: -0.05, 7: -0.15, 8: -0.3}, (1, 0.0), None),

	# Unique items
	EVEN_MORE_MAGICAL_HAMMER: ({-1: 0.3, 6: -0.1, 7: -0.2, 8: -0.25}, (1, 0.0), None),

	## Exp
	# Common items
	TRAINING_MANUAL: ({0: 0.1, 1: 0.05, 2: 0.05}, (2, 0.0), None),

	# Uncommon items
	CLAWS_OF_WISDOM: ({-1: 0.3, 6: -0.15, 7: -0.3, 8: -0.3}, (2, 0.0), None),
	EXPANDING_MIND: ({0: 0.15, 1: 0.1, 2: 0.1, 3: 0.05,}, (1, 0.0), None),
	WISE_MAN_S_COOKING_RECIPE: ({0: 0.25, 1: 0.25, 2: 0.15, 3: 0.05,}, (1, 0.0), None),
	CRYSTALLIZED_SCALES: ({0: 0.125, 1: 0.1, 2: 0.05,}, (2, 0.0), None),

	MAGIC_LINK: ({-1: 0.75, 6: -0.25, 7: -0.65, 8: -0.75}, (5, 0.0), None),

	VETERAN_S_TOME_OF_BATTLE: ({-1: 0.3, 5: -0.05, 6: -0.175, 7: -0.3, 8: -0.3}, (2, 0.0), None),
	KNOWING_MIND: ({-1: 0.65, 6: -0.15, 7: -0.4, 8: -0.65}, (2, 0.0), None),

	# Rare items
	WRITER_S_KNOWLEDGE: ({-1: 0.3, 6: -0.1, 7: -0.3, 8: -0.3}, (2, 0.0), None),
	SHINING_ROCK: ({0: 0.2, 1: 0.2, 2: 0.125, 3: 0.075, 4: 0.05}, (2, 0.0), None),
	SHARE_KNOWLEDGE: ({-1: 0.45, 6: -0.15, 7: -0.45, 8: -0.45}, (2, 0.0), None),
	BASICS_OF_CALCULUS: ({-1: 0.45, 6: -0.15, 7: -0.45, 8: -0.45}, (2, 0.0), None),
	BOOK_OF_KNOWLEDGE: ({-1: 0.35, 6: -0.1, 7: -0.35, 8: -0.35}, (2, 0.0), None),
	MINDLEECHER: ({-1: 0.5, 6: -0.15, 7: -0.5, 8: -0.5}, (2, 0.0), None),
	OLD_HUNTER: ({-1: 0.2, 6: -0.15, 7: -0.2, 8: -0.2}, (1, 0.0), None),

	# Unique items
	PRIEST_FIGURINE: ({0: 0.2, 1: 0.2, 2: 0.05}, (2, 0.0), None),
	FAITHFUL_STAFF: ({-1: 0.2, 6: -0.1, 7: -0.2, 8: -0.2}, (1, 0.0), None),
	LUNAR_ESSENCE: ({0: 0.45, 1: 0.45, 2: 0.375, 3: 0.3, 4: 0.2, 5: 0.125, 6: 0.05}, (2, 0.0), None),
	JEWELS_OF_THE_MOON: ({-1: 0.9, 6: -0.25, 7: -0.55, 8: -0.75}, (3, 0.0), None),

	## Gold

	# Uncommon items
	WANTED_LIST: ({0: 0.15, 1: 0.1, 2: 0.05}, (1, 0.0), None),
	PILLAGE_TOOLS: ({0: 0.15, 1: 0.15, 2: 0.1, 3: 0.05}, (1, 0.0), None),
	FLAWLESS_SAPPHIRE: ({0: 0.25, 1: 0.25, 2: 0.175, 3: 0.1, 4: 0.05,}, (2, 0.0), None),
	DIAMOND_OF_GREED: ({0: 0.15, 1: 0.15, 2: 0.1, 3: 0.05,}, (1, 0.0), None),
	BLOOD_CROWN: ({0: 0.25, 1: 0.25, 2: 0.175, 3: 0.1, 4: 0.05,}, (2, 0.0), None),

	SPEED_DEMON_S_REWARD: ({0: 0.25, 1: 0.25, 2: 0.25, 3: 0.075}, (30, 0.0), None),

	# Rare items
	ARMS_DEALER: ({0: 0.125, 1: 0.075}, (1, 0.0), None),
	CURRENCY_CONVERTER: ({0: 0.15, 1: 0.1, 2: 0.05}, (2, 0.0), None),

	ARCANE_SCRIPT: ({-1: 0.2, 6: -0.1, 7: -0.2, 8: -0.2}, (2, 0.0), None),

	# Unique items
	GOLDEN_TRIDENT: ({0: 0.2, 1: 0.2, 2: 0.2, 3: 0.15, 4: 0.05}, (1, 0.0), None),
	GOLDEN_DECORATION: ({0: 0.25, 1: 0.25, 2: 0.25, 3: 0.2, 4: 0.1, 5: 0.05,}, (3, 0.0), None),


	## Aura/enchant items

	# Rare items
	SWORD_OF_DECAY: ({-1: 1.0}, (1, 0.0), None),
	SWORD_OF_RECKONING: ({-1: 1.0}, (1, 0.0), None),

	SCROLL_OF_STRENGTH: ({-1: 0.2}, (1, 0.0), None),
	SCROLL_OF_SPEED: ({-1: 0.3}, (2, 0.0), None),

	RITUAL_TALISMAN: ({-1: 0.2}, (2, 0.0), None),

	COMMANDER: ({-1: 0.45}, (2, 0.0), None),

	CURSED_CLAW: ({-1: 0.55}, (2, 0.0), None),

	BLOODY_KEY: ({-1: 2.25}, (1, 0.0), None),

	MAGNETIC_FIELD: ({-1: 0.75}, (3, 0.0), None),

	ESSENCE_OF_ROT: ({-1: 2.5}, (1, 0.0), None),

	FORCEFIELD_GENERATOR: ({-1: 1.25}, (2, 0.0), None),

	# Unique items
	MIGHTY_TREE_S_ACORNS: ({-1: 1.35}, (2, 0.0), None),
	FLAG_OF_THE_ALLEGIANCE: ({-1: 0.7}, (1, 0.0), None),
	ARTIFACT_OF_SKADI: ({-1: 0.65}, (2, 0.0), None),
	CRUEL_TORCH: ({-1: 1.0}, (1, 0.0), None),
	WAR_DRUM: ({-1: 0.7,}, (3, 0.0), None),
	THE_DIVINE_WINGS_OF_TRAGEDY: ({-1: 1.8}, (3, 0.0), None),
	BHAAL_S_ESSENCE: ({-1: 0.9}, (2, 0.0), None),




	

	## Other items
	# Common items
	GIFT_OF_THE_WILD: ({-1: 0.1, 5: -0.1, 6: -0.1, 7: -0.1, 8: -0.1}, (1, 0.0), None),


	STRANGE_ITEM: ({-1: 1.0, 8: -1.0}, (30, 0.0), None),

	# Rare items
	HAUNTED_HAND: ({-1: 1.5, 7: -0.25, 8: -1.35}, (2, 0.0), None),
	STAFF_OF_THE_WILD_EQUUS: ({-1: 0.25, 6: -0.05, 7: -0.1, 8: -0.125}, (4, 0.0), None),
	WAND_OF_MANA_ZAP: ({-1: 0.25, 7: -0.05, 8: -0.1}, (3, 0.0), None),
	DIVINE_SHIELD: ({-1: 0.15}, (2, 0.0), None),
	STUNNER: ({-1: 0.275, 6: -0.025, 7: -0.075, 8: -0.1}, (4, 0.0), None),

	CHAMELEONS_SOUL: ({-1: 0.35, 6: -0.15, 7: -0.3, 8: -0.3}, (2, 0.0), None),

	# Unique items
	PORTABLE_TOMBSTONE: ({-1: 0.75}, (3, 0.0), None),
	SOUL_EXTRACTOR: ({-1: 0.4}, (1, 0.0), None),
	STASIS_TRAP: ({-1: 0.5, 6: -0.05, 7: -0.15, 8: -0.3}, (4, 0.0), None),
	LUCKY_GEM: ({-1: 0.65, 4: -0.05, 5: -0.1, 6: -0.2, 7: -0.45, 8: -0.6}, (4, 0.0), None),
	CHRONO_JUMPER: ({-1: 2.5}, (1, 0.0), None),
	EXCALIBUR: ({-1: 0.5, 6: -0.1, 7: -0.4, 8: -0.45}, (2, 0.0), None),
	DOOM_S_ENSIGN: ({-1: 0.6, 7: -0.25, 8: -0.25}, (2, 0.0), None),
	M_E_F_I_S_ROCKET: ({-1: 0.85, 8: -0.35}, (1, 0.0), None),
	DISTORTED_IDOL: ({-1: 4.0}, (3, 0.0), None),


}

def get_item_family_info(item_id: ITEM_ID) -> Optional[FAMILY_INFO]:
	"""
	Helper to safely retrieve family info for an item.
	"""
	val = USAGE_ITEM_VALUES.get(item_id)
	if not val:
		return None
	
	# Handle potentially missing tuple element if structure wasn't fully migrated in all entries (unlikely with new type hint but safe)
	if len(val) < 3:
		return None
	
	return val[2]


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
	"get_item_family_info",
	"FAMILY_RULES",
	"USAGE_ITEM_VALUES",
]
