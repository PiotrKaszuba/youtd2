from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Union, Optional, Set

from .models import Item, Recipe, Rarity
from .constants import ITEM_PROPERTIES_FILE, RECIPE_PROPERTIES_FILE, ITEM_ID


@dataclass(frozen=True)
class ItemDatabase:
	items: Dict[int, Item]

	def filter_items(
		self,
		level_min: Optional[int] = None,
		level_max: Optional[int] = None,
		rarity_whitelist: Optional[Set[Rarity]] = None,
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
