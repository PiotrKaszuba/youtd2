from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np


#########################
###    Data Model     ###
#########################


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


#########################
###   Data Loading    ###
#########################


@dataclass(frozen=True)
class ItemDatabase:
	items: Dict[int, Item]

	@classmethod
	def from_csv(cls, csv_path: Union[str, Path]) -> "ItemDatabase":
		path = Path(csv_path)
		items: Dict[int, Item] = {}

		with path.open(newline="", encoding="utf-8") as f:
			reader = csv.DictReader(f)
			for row in reader:
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


#########################
###   Constants       ###
#########################


# Maximum level bound for PRECIPITATE recipe (level-agnostic)
MAX_LEVEL_BOUND: int = 100000


def compute_avg_permanent_level(
	recipe: Recipe,
	item_db: ItemDatabase,
	explicit_item_ids: Sequence[int],
	aggregate_permanent_levels: Optional[int] = None,
) -> int:
	"""
	Recreates the Godot logic for average ingredient level but allows passing an
	aggregate sum of levels for unspecified permanent items.

	- Only permanent (regular) items contribute to the average.
	- The recipe's permanent_count defines how many permanent items there are in total.
	"""
	total_permanent_count = recipe.permanent_count

	if total_permanent_count <= 0:
		return 0

	explicit_permanent_levels: List[int] = []
	for item_id in explicit_item_ids:
		item = item_db.items.get(item_id)
		if item is None:
			continue
		if item.is_permanent:
			explicit_permanent_levels.append(item.required_wave_level)

	sum_explicit = sum(explicit_permanent_levels)

	if aggregate_permanent_levels is None:
		total_levels = sum_explicit
	else:
		total_levels = sum_explicit + aggregate_permanent_levels

	avg_level = int(total_levels // max(total_permanent_count, 1))

	return avg_level


def compute_level_bounds_for_recipe(
	recipe: Recipe,
	avg_permanent_level: int,
	random_bonus_mod: int,
) -> Tuple[int, int]:
	"""
	Compute lvl_min and lvl_max used for item pool selection.
	Matches HoradricCube.get_result_item_for_recipe logic, including PRECIPITATE.
	"""
	if recipe.id == RECIPE_PRECIPITATE:
		# PRECIPITATE – completely level agnostic
		return 0, MAX_LEVEL_BOUND

	lvl_min = avg_permanent_level + recipe.lvl_bonus_min + random_bonus_mod
	lvl_max = avg_permanent_level + recipe.lvl_bonus_max + random_bonus_mod
	return lvl_min, lvl_max


#########################
###    Item Pools     ###
#########################


def get_permanent_item_pool_bounded(
	item_db: ItemDatabase,
	rarity: int,
	lvl_min: int,
	lvl_max: int,
	exclude_item_ids: Optional[Sequence[int]] = None,
	with_fallback: bool = False,
) -> List[int]:
	"""
	Python mirror of ItemDropCalc.get_item_list_bounded.
	Returns IDs of regular items with the given rarity and level bounds.

	By default (with_fallback=False), this behaves like ItemDropCalc.get_item_list_bounded:
	it simply filters by rarity and level bounds and returns all matching item IDs.

	If with_fallback=True and the pool is empty, this applies the additional HoradricCube
	behavior from _get_transmuted_item: it lowers lvl_min by 10 repeatedly (up to 10
	times) until the pool becomes non-empty or gives up.
	"""
	if exclude_item_ids is None:
		exclude_item_ids = []
	exclude_set = {int(x) for x in exclude_item_ids}
	
	current_lvl_min = lvl_min
	loop_count = 0
	
	while True:
		pool: List[int] = []
		for item in item_db.items.values():
			if not item.is_permanent:
				continue
			if item.rarity != rarity:
				continue
			if item.id in exclude_set:
				continue
			level = item.required_wave_level
			if current_lvl_min <= level <= lvl_max:
				pool.append(item.id)
		
		if pool or not with_fallback:
			return pool
		
		current_lvl_min -= 10
		loop_count += 1
		if loop_count > 10:
			return []


def get_oil_and_consumable_pool(
	item_db: ItemDatabase,
	rarity: int,
	exclude_item_ids: Optional[Sequence[int]] = None,
) -> List[int]:
	"""
	Python mirror of ItemDropCalc.get_oil_and_consumables_list.
	"""
	if exclude_item_ids is None:
		exclude_item_ids = []
	exclude_set = {int(x) for x in exclude_item_ids}
	
	pool: List[int] = []
	for item in item_db.items.values():
		if not item.is_usable:
			continue
		if item.rarity != rarity:
			continue
		if item.id in exclude_set:
			continue
		pool.append(item.id)
	return pool


#########################
###  Decision Model   ###
#########################


@dataclass
class DecisionNode:
	"""
	Represents a random decision point.

	- name: semantic label for this decision (e.g. "luck", "item_choice").
	- probabilities: numpy array of shape (n,) summing to 1.
	- outcomes: list of either item IDs (int) or nested DecisionNode instances.
	"""

	name: str
	probabilities: np.ndarray
	outcomes: List[Union[int, "DecisionNode"]]

	def __post_init__(self) -> None:
		if len(self.probabilities) != len(self.outcomes):
			raise ValueError("probabilities and outcomes must have the same length")
		total = float(self.probabilities.sum())
		if total <= 0:
			raise ValueError("probabilities must sum to > 0")
		self.probabilities = self.probabilities / total

	def roll(self, rng: np.random.Generator) -> Union[int, "DecisionNode"]:
		"""
		Randomly pick a single outcome according to probabilities.
		"""
		index = int(rng.choice(len(self.outcomes), p=self.probabilities))
		return self.outcomes[index]
	
	def roll_to_item(self, rng: np.random.Generator) -> int:
		"""
		Recursively roll until an item ID (int) is reached.
		"""
		outcome = self.roll(rng)
		if isinstance(outcome, DecisionNode):
			return outcome.roll_to_item(rng)
		return int(outcome)


def collapse_to_item_distribution(node: DecisionNode) -> Dict[int, float]:
	"""
	Traverse a decision tree and produce a flat distribution over item IDs.
	Probabilities along the path are multiplied; items reached by multiple
	paths have their probabilities summed.
	"""
	result: Dict[int, float] = {}

	def _walk(current_node: DecisionNode, weight: float) -> None:
		for prob, outcome in zip(current_node.probabilities, current_node.outcomes):
			new_weight = weight * float(prob)
			if isinstance(outcome, DecisionNode):
				_walk(outcome, new_weight)
			else:
				item_id = int(outcome)
				result[item_id] = result.get(item_id, 0.0) + new_weight

	_walk(node, 1.0)
	return result


#########################
###  Luck & Choices   ###
#########################


LUCK_VALUES = np.array([-9, 0, 7, 18], dtype=int)
LUCK_WEIGHTS = np.array([20.0, 50.0, 20.0, 10.0], dtype=float)


def build_luck_node(name: str = "luck") -> DecisionNode:
	"""
	Luck decision as in HoradricCube._get_random_bonus_mod.
	"""
	probabilities = LUCK_WEIGHTS.copy()
	outcomes: List[int] = [int(v) for v in LUCK_VALUES]
	return DecisionNode(name=name, probabilities=probabilities, outcomes=outcomes)


def build_item_choice_node(
	item_ids: Sequence[int],
	name: str = "item_choice",
) -> DecisionNode:
	"""
	Uniform item choice among the given IDs.
	"""
	if not item_ids:
		raise ValueError("item_ids must not be empty")
	n = len(item_ids)
	probabilities = np.full(shape=(n,), fill_value=1.0 / n, dtype=float)
	outcomes = [int(i) for i in item_ids]
	return DecisionNode(name=name, probabilities=probabilities, outcomes=outcomes)


#########################
###  Recipe Result    ###
#########################


def build_single_result_decision_tree(
	recipe: Recipe,
	item_db: ItemDatabase,
	avg_permanent_level: int,
	result_rarity: int,
	explicit_ingredient_ids: Sequence[int],
) -> DecisionNode:
	"""
	Build a DecisionNode tree for a *single* result item of a recipe.

	- First decision: luck (bonus level modifier).
	- Second decision: uniform choice among candidate items given rarity and
	  level bounds for that luck outcome.
	- Ingredient item IDs are removed from candidate pools so that results
	  differ from ingredients, matching HoradricCube logic.
	"""
	explicit_set = {int(x) for x in explicit_ingredient_ids}

	luck_node = build_luck_node()
	luck_children: List[DecisionNode] = []

	for bonus_mod in LUCK_VALUES:
		lvl_min, lvl_max = compute_level_bounds_for_recipe(
			recipe=recipe,
			avg_permanent_level=avg_permanent_level,
			random_bonus_mod=int(bonus_mod),
		)

		if recipe.result_item_type == ResultItemType.USABLE:
			candidate_pool = get_oil_and_consumable_pool(
				item_db, result_rarity, exclude_item_ids=explicit_ingredient_ids
			)
		elif recipe.result_item_type == ResultItemType.PERMANENT:
			candidate_pool = get_permanent_item_pool_bounded(
				item_db=item_db,
				rarity=result_rarity,
				lvl_min=lvl_min,
				lvl_max=lvl_max,
				exclude_item_ids=explicit_ingredient_ids,
				with_fallback=True,
			)
		else:
			candidate_pool = []

		if not candidate_pool:
			# No available items – represent as a degenerate node pointing to 0.
			# Note: 0 is used as sentinel value for empty pool (matches Godot behavior).
			child = build_item_choice_node([0], name="item_choice_empty")
		else:
			child = build_item_choice_node(candidate_pool, name="item_choice")

		luck_children.append(child)

	return DecisionNode(
		name="luck_then_item",
		probabilities=LUCK_WEIGHTS.copy(),
		outcomes=luck_children,
	)


#########################
###    Public API     ###
#########################


def roll_single_result(
	recipe: Recipe,
	item_db: ItemDatabase,
	avg_permanent_level: int,
	result_rarity: int,
	explicit_ingredient_ids: Sequence[int],
	rng: Optional[np.random.Generator] = None,
) -> int:
	"""
	Roll a single result item, mirroring the Horadric cube semantics for
	random bonus modifier + candidate pool selection.
	"""
	if rng is None:
		rng = np.random.default_rng()

	tree = build_single_result_decision_tree(
		recipe=recipe,
		item_db=item_db,
		avg_permanent_level=avg_permanent_level,
		result_rarity=result_rarity,
		explicit_ingredient_ids=explicit_ingredient_ids,
	)

	return tree.roll_to_item(rng)


def get_single_result_distribution(
	recipe: Recipe,
	item_db: ItemDatabase,
	avg_permanent_level: int,
	result_rarity: int,
	explicit_ingredient_ids: Sequence[int],
) -> Dict[int, float]:
	"""
	Enumerate all luck outcomes and item choices to get a full probability
	distribution over result item IDs for a *single* result slot.

	Note: item ID 0 (if present) represents an empty pool / failure case, matching
	Godot's use of 0 as the sentinel "no item" value.
	"""
	tree = build_single_result_decision_tree(
		recipe=recipe,
		item_db=item_db,
		avg_permanent_level=avg_permanent_level,
		result_rarity=result_rarity,
		explicit_ingredient_ids=explicit_ingredient_ids,
	)
	return collapse_to_item_distribution(tree)



def find_best_avg_level_for_item(
	target_item_id: int,
	recipe: Recipe,
	item_db: ItemDatabase,
	avg_level_range: Iterable[int],
	explicit_ingredient_ids: Optional[Sequence[int]] = None,
) -> Tuple[Optional[int], Dict[int, float]]:
	"""
	Scan a range of average ingredient levels and find at which level the
	probability of obtaining target_item_id is maximal for a single result
	slot of the given recipe.

	- explicit_ingredient_ids: items to be treated as ingredients and removed
	  from result pools; does not affect the average directly here.

	"""
	if explicit_ingredient_ids is None:
		explicit_ingredient_ids = []

	target_item = item_db.items.get(int(target_item_id))
	if target_item is None:
		raise ValueError(f"Unknown target item id: {target_item_id}")
	
	# result rarity is the same as the target item rarity
	result_rarity = target_item.rarity

	prob_by_level: Dict[int, float] = {}
	best_level: Optional[int] = None
	best_prob: float = 0.0

	for avg_level in avg_level_range:
		dist = get_single_result_distribution(
			recipe=recipe,
			item_db=item_db,
			avg_permanent_level=avg_level,
			result_rarity=result_rarity,
			explicit_ingredient_ids=explicit_ingredient_ids,
		)
		prob = dist.get(target_item_id, 0.0)
		prob_by_level[avg_level] = prob
		if prob > best_prob:
			best_prob = prob
			best_level = avg_level

	return best_level, prob_by_level


#########################
###   Recipe IDs      ###
#########################


# Recipe IDs matching recipe_properties.csv and HoradricCube.Recipe enum.
RECIPE_NONE: int = 0
RECIPE_REBREW: int = 1
RECIPE_DISTILL: int = 2
RECIPE_REASSEMBLE: int = 3
RECIPE_PERFECT: int = 4
RECIPE_LIQUEFY: int = 5
RECIPE_PRECIPITATE: int = 6
RECIPE_IMBUE: int = 7


#########################
###   Named Item IDs  ###
#########################


# Commonly referenced item IDs for convenience in analyses.
ENCHANTED_MINING_PICK: int = 8
HAUNTED_HAND: int = 246
STRANGE_ITEM: int = 233


#########################
###      CLI Demo     ###
#########################


def _load_default_databases() -> Tuple[ItemDatabase, RecipeDatabase]:
	root = Path(__file__).resolve().parent.parent
	item_db = ItemDatabase.from_csv(root / "data" / "item_properties.csv")
	recipe_db = RecipeDatabase.from_csv(root / "data" / "recipe_properties.csv")
	return item_db, recipe_db


def main() -> None:
	item_db, recipe_db = _load_default_databases()

	##
	item = STRANGE_ITEM
	recipe = RECIPE_PERFECT
	level_range = range(0, 120)
	##

	best_level, curve = find_best_avg_level_for_item(
		target_item_id=item,
		recipe=recipe_db.recipes[recipe],
		item_db=item_db,
		avg_level_range=level_range,
		explicit_ingredient_ids=[],
	)

	print(f"Best avg ingredient level for item {item}: {best_level}")
	if best_level is not None:
		print(f"Probability at best level: {curve[best_level]*100:.2f}%")

	# print the curve
	print(f"Probabilities by level:")
	print(f"Level\tProbability")
	for level, prob in curve.items():
		print(f"Level {level}: {prob*100:.2f}%")


if __name__ == "__main__":
	main()


