from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Union, Optional, Set

from .models import Item, Recipe, Rarity
from .constants import ITEM_PROPERTIES_FILE, RECIPE_PROPERTIES_FILE, ITEM_ID


@dataclass(frozen=True)
class ItemDatabase:
	items: Dict[int, Item]
	_hash: Optional[int] = field(default=None, repr=False, compare=False)

	def __hash__(self) -> int:
		if self._hash is None:
			# Hash based on sorted keys and item content hashes (if Item is hashable)
			# Assuming Item is immutable or we trust it enough for this session.
			# We use a frozenset of items for order independence.
			# Since Item doesn't implement __hash__ yet, we might need to or use id/content.
			# Actually, let's just hash the sorted IDs for filter identification, 
			# and maybe length.
			# A truly safe hash would hash all item contents.
			# For now, let's hash sorted item IDs as a proxy for "filtered subset".
			# If item *properties* change, this won't catch it, but for filtering it's fine.
			self.__object_setattr__("_hash", hash(tuple(sorted(self.items.keys()))))
		return self._hash

	def __object_setattr__(self, name, value):
		# Helper for frozen dataclass setattr
		object.__setattr__(self, name, value)

	def filter_items(
		self,
		level_min: Optional[int] = None,
		level_max: Optional[int] = None,
		rarity_whitelist: Optional[Set[Rarity]] = None,
		include_permanent: bool = True,
		include_usable: bool = True,
		remove_item_ids: Set[ITEM_ID] = None ) -> ItemDatabase:
		
		filtered_items: Dict[int, Item] = {}
		for item_id, item in self.items.items():
			if remove_item_ids and item_id in remove_item_ids:
				continue
			if level_min and item.required_wave_level < level_min:
				continue
			if level_max and item.required_wave_level > level_max:
				continue
			if rarity_whitelist and item.rarity not in rarity_whitelist:
				continue
			if not include_permanent and item.is_permanent:
				continue
			if not include_usable and item.is_usable:
				continue
			filtered_items[item_id] = item
		return ItemDatabase(items=filtered_items)

	@staticmethod
	def _load_default_database() -> "ItemDatabase":
		return ItemDatabase.from_csv(ITEM_PROPERTIES_FILE)

	@classmethod
	def from_csv(cls, csv_path: Union[str, Path]) -> "ItemDatabase":
		path = Path(csv_path)
		items: Dict[int, Item] = {}

		with path.open(newline="", encoding="utf-8") as f:
			reader = csv.DictReader(f)
			for row in reader:
				# Skip rows without ID
				if not row.get("id"):
					continue

				item_id = int(row["id"])
				item = Item(
					id=item_id,
					name_english=row.get("name english", ""),
					item_type=row.get("type", "").strip().lower(),
					author=row.get("author", ""),
					rarity=Rarity.from_string(row.get("rarity", "common")),
					cost=int(row.get("cost", 0)) if row.get("cost") and row["cost"].isdigit() else 0,
					required_wave_level=int(row.get("required wave level", 0))
					if row.get("required wave level", "").isdigit()
					else 0,
					specials=row.get("specials", ""),
					ability_list=row.get("ability list", ""),
					aura_list=row.get("aura list", ""),
					autocast_list=row.get("autocast list", ""),
					script_path=row.get("script path", ""),
					icon=row.get("icon", ""),
					name=row.get("name", ""),
					description=row.get("description", ""),
				)
				items[item_id] = item

		return cls(items=items)


@dataclass(frozen=True)
class RecipeDatabase:
	recipes: Dict[int, Recipe]

	@staticmethod
	def _load_default_database() -> "RecipeDatabase":
		return RecipeDatabase.from_csv(RECIPE_PROPERTIES_FILE)

	@classmethod
	def from_csv(cls, csv_path: Union[str, Path]) -> "RecipeDatabase":
		path = Path(csv_path)
		recipes: Dict[int, Recipe] = {}

		with path.open(newline="", encoding="utf-8") as f:
			reader = csv.DictReader(f)
			for row in reader:
				if not row.get("id"):
					continue

				recipe_id = int(row["id"])
				unlocked_str = row.get("unlocked by backpacker", "FALSE").strip().upper()

				recipe = Recipe(
					id=recipe_id,
					name_english=row.get("name english", ""),
					permanent_count=int(row.get("permanent count", 0) or 0),
					usable_count=int(row.get("usable count", 0) or 0),
					result_item_type=row.get("result item type", "").strip().lower(),
					result_count=int(row.get("result count", 0) or 0),
					rarity_change=int(row.get("rarity change", 0) or 0),
					lvl_bonus_min=int(row.get("lvl bonus min", 0) or 0),
					lvl_bonus_max=int(row.get("lvl bonus max", 0) or 0),
					unlocked_by_backpacker=unlocked_str == "TRUE",
					display_name=row.get("display name", ""),
					description=row.get("description", ""),
				)
				recipes[recipe_id] = recipe

		return cls(recipes=recipes)


def load_default_databases() -> (ItemDatabase, RecipeDatabase):
	item_db = ItemDatabase._load_default_database()
	recipe_db = RecipeDatabase._load_default_database()
	return item_db, recipe_db
