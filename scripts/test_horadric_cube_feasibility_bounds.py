from __future__ import annotations

import math

from horadric_cube.constants import ENCHANTED_MINING_PICK, RECIPE_REASSEMBLE
from horadric_cube.db import load_default_databases
from horadric_cube.levels_and_pools import (
	compute_missing_permanent_sum_bounds,
	infer_ingredient_rarity,
)
from horadric_cube.models import Rarity


def _load_dbs():
	return load_default_databases()


def test_compute_missing_permanent_sum_bounds_basic():
	item_db, recipe_db = _load_dbs()
	recipe = recipe_db.recipes[RECIPE_REASSEMBLE]

	# Choose an average level where permanents exist.
	avg_level = 40

	bounds = compute_missing_permanent_sum_bounds(
		recipe=recipe,
		item_db=item_db,
		explicit_item_ids=[],
		avg_permanent_level=avg_level,
	)

	assert bounds is not None
	sum_rest_min, sum_rest_max, missing_count = bounds

	assert missing_count == recipe.permanent_count
	assert sum_rest_min <= sum_rest_max


def test_compute_missing_permanent_sum_bounds_with_explicit():
	item_db, recipe_db = _load_dbs()
	recipe = recipe_db.recipes[RECIPE_REASSEMBLE]

	# Use a known permanent item as explicit ingredient.
	explicit_ids = [ENCHANTED_MINING_PICK]
	explicit_level = item_db.items[ENCHANTED_MINING_PICK].required_wave_level

	avg_level = explicit_level  # simple case

	bounds = compute_missing_permanent_sum_bounds(
		recipe=recipe,
		item_db=item_db,
		explicit_item_ids=explicit_ids,
		avg_permanent_level=avg_level,
	)

	assert bounds is not None
	sum_rest_min, sum_rest_max, missing_count = bounds

	# We know at least one permanent slot is used by the explicit item.
	assert missing_count == recipe.permanent_count - 1
	assert sum_rest_min <= sum_rest_max


def test_compute_missing_permanent_sum_bounds_impossible():
	item_db, recipe_db = _load_dbs()
	recipe = recipe_db.recipes[RECIPE_REASSEMBLE]

	# Use more explicit permanents than the recipe allows by duplicating the same ID.
	explicit_ids = [ENCHANTED_MINING_PICK] * (recipe.permanent_count + 1)

	bounds = compute_missing_permanent_sum_bounds(
		recipe=recipe,
		item_db=item_db,
		explicit_item_ids=explicit_ids,
		avg_permanent_level=10,
	)

	assert bounds is None


def test_infer_ingredient_rarity_clamping():
	item_db, recipe_db = _load_dbs()
	recipe = recipe_db.recipes[RECIPE_REASSEMBLE]

	# Take a target item at rare rarity.
	target_rarity = Rarity.RARE

	ingredient_rarity = infer_ingredient_rarity(target_rarity, recipe)

	# Should be within valid rarity bounds.
	assert Rarity.COMMON <= ingredient_rarity <= Rarity.UNIQUE


