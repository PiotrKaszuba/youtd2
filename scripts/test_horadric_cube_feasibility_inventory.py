from __future__ import annotations

from horadric_cube.feasibility import is_avg_level_feasible, get_feasible_avg_levels_for_recipe
from horadric_cube.models import Item, ItemType, Recipe, ResultItemType, Rarity
from horadric_cube.db import ItemDatabase


def _build_synthetic_db() -> ItemDatabase:
	items = {
		1: Item(
			id=1,
			name_english="Perm L2",
			item_type=ItemType.REGULAR,
			author="test",
			rarity=Rarity.RARE,
			cost=0,
			required_wave_level=2,
			specials="",
			ability_list="",
			aura_list="",
			autocast_list="",
			script_path="",
			icon="",
			name="Perm L2",
			description="",
		),
		2: Item(
			id=2,
			name_english="Perm L3",
			item_type=ItemType.REGULAR,
			author="test",
			rarity=Rarity.RARE,
			cost=0,
			required_wave_level=3,
			specials="",
			ability_list="",
			aura_list="",
			autocast_list="",
			script_path="",
			icon="",
			name="Perm L3",
			description="",
		),
		3: Item(
			id=3,
			name_english="Perm L5",
			item_type=ItemType.REGULAR,
			author="test",
			rarity=Rarity.RARE,
			cost=0,
			required_wave_level=5,
			specials="",
			ability_list="",
			aura_list="",
			autocast_list="",
			script_path="",
			icon="",
			name="Perm L5",
			description="",
		),
		99: Item(
			id=99,
			name_english="Target",
			item_type=ItemType.REGULAR,
			author="test",
			rarity=Rarity.RARE,
			cost=0,
			required_wave_level=10,
			specials="",
			ability_list="",
			aura_list="",
			autocast_list="",
			script_path="",
			icon="",
			name="Target",
			description="",
		),
	}
	return ItemDatabase(items=items)


def _build_recipe() -> Recipe:
	return Recipe(
		id=1,
		name_english="Test Recipe",
		permanent_count=3,
		usable_count=0,
		result_item_type=ResultItemType.PERMANENT,
		result_count=1,
		rarity_change=0,
		lvl_bonus_min=0,
		lvl_bonus_max=0,
		unlocked_by_backpacker=False,
		display_name="Test Recipe",
		description="",
	)


def test_is_avg_level_feasible_positive():
	item_db = _build_synthetic_db()
	recipe = _build_recipe()

	# Inventory has exactly one copy of each permanent.
	inventory = {1: 1, 2: 1, 3: 1}

	avg_level = 3  # sum range: [9, 11], and 2+3+5=10 is achievable.

	assert is_avg_level_feasible(
		target_item_id=99,
		recipe=recipe,
		item_db=item_db,
		inventory=inventory,
		avg_permanent_level=avg_level,
		explicit_ingredient_ids=[],
	)


def test_is_avg_level_feasible_negative_insufficient_levels():
	item_db = _build_synthetic_db()
	recipe = _build_recipe()

	inventory = {1: 1, 2: 1, 3: 1}

	avg_level = 6  # sum range: [18, 23], but we only have 2+3+5=10 total.

	assert not is_avg_level_feasible(
		target_item_id=99,
		recipe=recipe,
		item_db=item_db,
		inventory=inventory,
		avg_permanent_level=avg_level,
		explicit_ingredient_ids=[],
	)


def test_get_feasible_avg_levels_for_recipe_matches_feasibility():
	item_db = _build_synthetic_db()
	recipe = _build_recipe()

	inventory = {1: 1, 2: 1, 3: 1}

	levels = list(range(0, 10))
	feasible_levels = get_feasible_avg_levels_for_recipe(
		target_item_id=99,
		recipe=recipe,
		item_db=item_db,
		inventory=inventory,
		avg_level_range=levels,
		explicit_ingredient_ids=[],
	)

	# avg_level = 3 should be feasible; 6 should not.
	assert 3 in feasible_levels
	assert 6 not in feasible_levels


