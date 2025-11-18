from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .db import ItemDatabase
from .models import Recipe, Rarity
from .constants import RECIPE_PRECIPITATE


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


def compute_missing_permanent_sum_bounds(
	recipe: Recipe,
	item_db: ItemDatabase,
	explicit_item_ids: Sequence[int],
	avg_permanent_level: int,
) -> Optional[Tuple[int, int, int]]:
	"""
	Compute the feasible range of total levels contributed by *non-explicit*
	permanent ingredients for a given average permanent level.

	Returns (sum_rest_min, sum_rest_max, missing_count) or None if the setup
	is structurally impossible (e.g. too many explicit permanents or no
	permanent slots in the recipe).
	"""
	total_permanent_count = recipe.permanent_count
	if total_permanent_count <= 0:
		return None

	# Collect explicit permanent levels.
	explicit_permanent_levels: List[int] = []
	for item_id in explicit_item_ids:
		item = item_db.items.get(int(item_id))
		if item is None or not item.is_permanent:
			continue
		explicit_permanent_levels.append(item.required_wave_level)

	explicit_count = len(explicit_permanent_levels)
	if explicit_count > total_permanent_count:
		# More explicit permanents than slots – impossible configuration.
		return None

	missing_count = total_permanent_count - explicit_count
	sum_explicit = sum(explicit_permanent_levels)

	if missing_count == 0:
		# No missing permanents – check if the explicit ones alone yield this average.
		avg_from_explicit = int(sum_explicit // max(total_permanent_count, 1))
		if avg_from_explicit != avg_permanent_level:
			return None
		return 0, 0, 0

	# Derive bounds from:
	# avg_permanent_level <= (sum_explicit + sum_rest) / total_permanent_count < avg_permanent_level + 1
	sum_rest_min = max(0, total_permanent_count * avg_permanent_level - sum_explicit)
	sum_rest_max = total_permanent_count * (avg_permanent_level + 1) - 1 - sum_explicit

	if sum_rest_min > sum_rest_max:
		return None

	return sum_rest_min, sum_rest_max, missing_count


def infer_ingredient_rarity(target_rarity: int, recipe: Recipe) -> int:
	"""
	Infer ingredient rarity from target rarity and recipe.rarity_change.

	Result is clamped to the valid rarity bounds defined by Rarity.
	"""
	raw_rarity = target_rarity - recipe.rarity_change
	return max(Rarity.COMMON, min(Rarity.UNIQUE, raw_rarity))


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



