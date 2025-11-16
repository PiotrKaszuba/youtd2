from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from horadric_cube_sim import (
	ENCHANTED_MINING_PICK,
	ItemDatabase,
	Rarity,
	RECIPE_REASSEMBLE,
	RecipeDatabase,
	find_best_avg_level_for_item,
	get_permanent_item_pool_bounded,
	get_single_result_distribution,
)


def _load_dbs():
	root = Path(__file__).resolve().parent.parent
	item_db = ItemDatabase.from_csv(root / "data" / "item_properties.csv")
	recipe_db = RecipeDatabase.from_csv(root / "data" / "recipe_properties.csv")
	return item_db, recipe_db


def test_item_and_recipe_loading():
	item_db, recipe_db = _load_dbs()

	assert ENCHANTED_MINING_PICK in item_db.items
	assert RECIPE_REASSEMBLE in recipe_db.recipes  # Reassemble


def test_permanent_pool_contains_pick():
	item_db, _ = _load_dbs()

	pool = get_permanent_item_pool_bounded(
		item_db=item_db,
		rarity=Rarity.RARE,
		lvl_min=40,
		lvl_max=50,
	)

	assert ENCHANTED_MINING_PICK in pool


def test_distribution_sums_to_one():
	item_db, recipe_db = _load_dbs()
	recipe = recipe_db.recipes[RECIPE_REASSEMBLE]  # Reassemble

	dist = get_single_result_distribution(
		recipe=recipe,
		item_db=item_db,
		avg_permanent_level=44,
		result_rarity=Rarity.RARE,
		explicit_ingredient_ids=[],
	)

	total_prob = sum(dist.values())
	assert math.isclose(total_prob, 1.0, rel_tol=1e-6)


def test_main_scenario_best_level_and_prob():
	item_db, recipe_db = _load_dbs()
	recipe = recipe_db.recipes[RECIPE_REASSEMBLE]  # Reassemble

	best_level, curve = find_best_avg_level_for_item(
		target_item_id=ENCHANTED_MINING_PICK,
		recipe=recipe,
		item_db=item_db,
		avg_level_range=range(0, 120),
		explicit_ingredient_ids=[],
	)

	# These values should stay stable unless the underlying drop logic or data changes.
	assert best_level == 29
	assert math.isclose(curve[best_level], 0.08095238095238096, rel_tol=1e-9)


