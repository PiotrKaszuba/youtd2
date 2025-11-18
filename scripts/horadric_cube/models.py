from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


class Rarity:
	COMMON = 0
	UNCOMMON = 1
	RARE = 2
	UNIQUE = 3

	_STRING_TO_VALUE = {
		"common": COMMON,
		"uncommon": UNCOMMON,
		"rare": RARE,
		"unique": UNIQUE,
	}

	_VALUE_TO_STRING = {v: k for k, v in _STRING_TO_VALUE.items()}

	@classmethod
	def from_string(cls, value: str) -> int:
		value_lower = value.strip().lower()
		if value_lower not in cls._STRING_TO_VALUE:
			raise ValueError(f"Unknown rarity string: {value}")
		return cls._STRING_TO_VALUE[value_lower]

	@classmethod
	def to_string(cls, value: int) -> str:
		return cls._VALUE_TO_STRING[value]


class ItemType:
	REGULAR = "regular"
	OIL = "oil"
	CONSUMABLE = "consumable"


@dataclass(frozen=True)
class Item:
	id: int
	name_english: str
	item_type: str
	author: str
	rarity: int
	cost: int
	required_wave_level: int
	specials: str
	ability_list: str
	aura_list: str
	autocast_list: str
	script_path: str
	icon: str
	name: str
	description: str

	@property
	def is_permanent(self) -> bool:
		return self.item_type == ItemType.REGULAR

	@property
	def is_usable(self) -> bool:
		return self.item_type in (ItemType.OIL, ItemType.CONSUMABLE)


class ResultItemType:
	PERMANENT = "permanent"
	USABLE = "usable"
	NONE = "none"


@dataclass(frozen=True)
class Recipe:
	id: int
	name_english: str
	permanent_count: int
	usable_count: int
	result_item_type: str
	result_count: int
	rarity_change: int
	lvl_bonus_min: int
	lvl_bonus_max: int
	unlocked_by_backpacker: bool
	display_name: str
	description: str

	@property
	def uses_permanents(self) -> bool:
		return self.permanent_count > 0

	@property
	def uses_usables(self) -> bool:
		return self.usable_count > 0
