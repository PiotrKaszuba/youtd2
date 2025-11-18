from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .db import ItemDatabase, RecipeDatabase
from .decision_tree import (
	DecisionNode,
	LUCK_VALUES,
	LUCK_WEIGHTS,
	build_item_choice_node,
	build_luck_node,
	collapse_to_item_distribution,
)
from .levels_and_pools import (
	compute_level_bounds_for_recipe,
	get_oil_and_consumable_pool,
	get_permanent_item_pool_bounded,
)
from .models import Recipe, ResultItemType
from .feasibility import (
	get_feasible_avg_levels_for_recipe,
)
from .constants import Inventory


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
) -> Tuple[Optional[int], Dict[int, float], Dict[int, Dict[int, float]]]:
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

	avg_level_dist_map: Dict[int, Dict[int, float]] = {}

	for avg_level in avg_level_range:
		dist = get_single_result_distribution(
			recipe=recipe,
			item_db=item_db,
			avg_permanent_level=avg_level,
			result_rarity=result_rarity,
			explicit_ingredient_ids=explicit_ingredient_ids,
		)
		avg_level_dist_map[avg_level] = dist
		prob = dist.get(target_item_id, 0.0)
		prob_by_level[avg_level] = prob
		if prob > best_prob:
			best_prob = prob
			best_level = avg_level

	return best_level, prob_by_level, avg_level_dist_map


@dataclass
class HoradricEngine:
	"""
	Thin wrapper around the core functions, grouping item/recipe databases.

	This is future-proofed for value-based optimization while currently
	remaining a light façade over the existing functional API.
	"""

	item_db: ItemDatabase
	recipe_db: RecipeDatabase

	@staticmethod
	def create_horadric_engine(
		item_db: ItemDatabase = None,
		recipe_db: RecipeDatabase = None,
	) -> HoradricEngine:
		if item_db is None:
			item_db = ItemDatabase._load_default_database()
		if recipe_db is None:
			recipe_db = RecipeDatabase._load_default_database()
		return HoradricEngine(item_db=item_db, recipe_db=recipe_db)

	def get_single_result_distribution(
		self,
		recipe_id: int,
		avg_permanent_level: int,
		result_rarity: int,
		explicit_ingredient_ids: Sequence[int],
	) -> Dict[int, float]:
		recipe = self.recipe_db.recipes[recipe_id]
		return get_single_result_distribution(
			recipe=recipe,
			item_db=self.item_db,
			avg_permanent_level=avg_permanent_level,
			result_rarity=result_rarity,
			explicit_ingredient_ids=explicit_ingredient_ids,
		)

	def find_best_avg_level_for_item(
		self,
		target_item_id: int,
		recipe_id: int,
		avg_level_range: Iterable[int],
		explicit_ingredient_ids: Optional[Sequence[int]] = None,
	) -> Tuple[Optional[int], Dict[int, float]]:
		recipe = self.recipe_db.recipes[recipe_id]
		return find_best_avg_level_for_item(
			target_item_id=target_item_id,
			recipe=recipe,
			item_db=self.item_db,
			avg_level_range=avg_level_range,
			explicit_ingredient_ids=explicit_ingredient_ids,
		)

	def get_feasible_avg_levels_for_item(
		self,
		target_item_id: int,
		recipe_id: int,
		inventory: Optional[Inventory],
		avg_level_range: Iterable[int],
		explicit_ingredient_ids: Sequence[int],
	) -> List[int]:
		recipe = self.recipe_db.recipes[recipe_id]
		return get_feasible_avg_levels_for_recipe(
			target_item_id=target_item_id,
			recipe=recipe,
			item_db=self.item_db,
			inventory=inventory,
			avg_level_range=avg_level_range,
			explicit_ingredient_ids=explicit_ingredient_ids,
		)

	def find_best_avg_level_for_item_with_inventory(
		self,
		target_item_id: int,
		recipe_id: int,
		inventory: Optional[Inventory],
		avg_level_range: Iterable[int],
		explicit_ingredient_ids: Sequence[int],
	) -> Tuple[Optional[int], Dict[int, float], Dict[int, Dict[int, float]]]:
		"""
		Inventory-aware variant of best-level search.

		Filters average levels by feasibility and then reuses the existing
		distribution logic to choose the level with the highest probability
		of the target item.
		"""
		recipe = self.recipe_db.recipes[recipe_id]

		feasible_levels = get_feasible_avg_levels_for_recipe(
			target_item_id=target_item_id,
			recipe=recipe,
			item_db=self.item_db,
			inventory=inventory,
			avg_level_range=avg_level_range,
			explicit_ingredient_ids=explicit_ingredient_ids,
		)

		if not feasible_levels:
			return None, {}, {}

		target_item = self.item_db.items.get(int(target_item_id))
		if target_item is None:
			return None, {}, {}

		result_rarity = target_item.rarity

		feasible_distributions: Dict[int, Dict[int, float]] = {}
		prob_by_level: Dict[int, float] = {}
		best_level: Optional[int] = None
		best_prob: float = 0.0

		for level in feasible_levels:
			dist = get_single_result_distribution(
				recipe=recipe,
				item_db=self.item_db,
				avg_permanent_level=level,
				result_rarity=result_rarity,
				explicit_ingredient_ids=explicit_ingredient_ids,
			)
			feasible_distributions[level] = dist
			prob = dist.get(target_item_id, 0.0)
			prob_by_level[level] = prob
			if prob > best_prob:
				best_prob = prob
				best_level = level

		return best_level, prob_by_level, feasible_distributions


