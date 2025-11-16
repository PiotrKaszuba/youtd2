from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from horadric_cube_sim import (
	ENCHANTED_MINING_PICK,
	ItemDatabase,
	Rarity,
	RecipeDatabase,
	get_permanent_item_pool_bounded,
	get_single_result_distribution,
)


def _load_dbs():
	root = Path(__file__).resolve().parent
	item_db = ItemDatabase.from_csv(root / "data" / "item_properties.csv")
	recipe_db = RecipeDatabase.from_csv(root / "data" / "recipe_properties.csv")
	return item_db, recipe_db


def test_item_and_recipe_loading():
	item_db, recipe_db = _load_dbs()

	assert ENCHANTED_MINING_PICK in item_db.items
	assert 3 in recipe_db.recipes  # Reassemble


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
	recipe = recipe_db.recipes[3]  # Reassemble

	dist = get_single_result_distribution(
		recipe=recipe,
		item_db=item_db,
		avg_permanent_level=44,
		result_rarity=Rarity.RARE,
		explicit_ingredient_ids=[],
	)

	total_prob = sum(dist.values())
	assert math.isclose(total_prob, 1.0, rel_tol=1e-6)


