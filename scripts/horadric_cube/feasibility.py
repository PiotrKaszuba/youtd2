from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

from .constants import Inventory
from .db import ItemDatabase
from .k_sum_with_reuse import find_k_sum_with_reuse
from .levels_and_pools import compute_missing_permanent_sum_bounds, infer_ingredient_rarity
from .models import Item, Recipe


def _clone_inventory(inventory: Optional[Inventory]) -> Inventory:
	if inventory is None:
		return {}
	return dict(inventory)


def _consume_explicit_ingredients(
	item_db: ItemDatabase,
	inventory: Inventory,
	explicit_item_ids: Sequence[int],
) -> Optional[Inventory]:
	"""
	Consume one unit in inventory for each explicit ingredient ID.

	Returns a new inventory dict or None if any explicit ingredient cannot be
	satisfied from the inventory counts.
	"""
	remaining = _clone_inventory(inventory)

	for item_id in explicit_item_ids:
		item_id_int = int(item_id)
		if item_id_int not in item_db.items:
			return None

		current = remaining.get(item_id_int, 0)
		if current <= 0:
			return None
		remaining[item_id_int] = current - 1

	return remaining


def _build_permanent_candidates(
	item_db: ItemDatabase,
	inventory: Optional[Inventory],
	explicit_item_ids: Sequence[int],
	ingredient_rarity: int,
) -> List[Item]:
	explicit_set = {int(x) for x in explicit_item_ids}
	candidates: List[Item] = []

	for item in item_db.items.values():
		if not item.is_permanent:
			continue
		if item.rarity != ingredient_rarity:
			continue
		if item.id in explicit_set:
			continue
		if inventory is not None and inventory.get(item.id, 0) <= 0:
			continue
		candidates.append(item)

	return candidates


def _build_level_to_ids(
	candidates: List[Item],
	inventory: Optional[Inventory],
) -> Dict[int, List[int]]:
	level_to_ids: Dict[int, List[int]] = {}

	for item in candidates:
		count = inventory.get(item.id, 1) if inventory is not None else 1
		if count <= 0:
			continue
		bucket = level_to_ids.setdefault(item.required_wave_level, [])
		for _ in range(count):
			bucket.append(item.id)

	return level_to_ids


def _assign_levels_to_items(
	levels: List[int],
	level_to_ids: Dict[int, List[int]],
) -> Optional[List[int]]:
	"""
	Try to map a multiset of levels to concrete item IDs under inventory bounds.
	"""
	local_map: Dict[int, List[int]] = {lvl: ids.copy() for lvl, ids in level_to_ids.items()}
	assigned: List[int] = []

	for lvl in levels:
		bucket = local_map.get(lvl)
		if not bucket:
			return None
		item_id = bucket.pop()
		assigned.append(item_id)

	return assigned


def is_avg_level_feasible(
	target_item_id: int,
	recipe: Recipe,
	item_db: ItemDatabase,
	inventory: Optional[Inventory],
	avg_permanent_level: int,
	explicit_ingredient_ids: Sequence[int],
) -> bool:
	"""
	Check whether a recipe is feasible for a given average permanent level,
	given an inventory and explicit ingredient IDs.

	This respects:
	- recipe.permanent_count and usable_count
	- rarity_change (via ingredient rarity inference)
	- inventory counts for both explicit and non-explicit ingredients
	"""
	if recipe.permanent_count <= 0:
		# For now we only handle recipes that use permanents in the average.
		return False

	target_item = item_db.items.get(int(target_item_id))
	if target_item is None:
		return False

	ingredient_rarity = infer_ingredient_rarity(target_item.rarity, recipe)

	# Work on a copy of inventory so callers can reuse their structure.
	working_inventory = _clone_inventory(inventory)
	if inventory is not None:
		consumed = _consume_explicit_ingredients(item_db, working_inventory, explicit_ingredient_ids)
		if consumed is None:
			return False
		working_inventory = consumed

	# Structural bounds for missing permanent levels.
	bounds = compute_missing_permanent_sum_bounds(
		recipe=recipe,
		item_db=item_db,
		explicit_item_ids=explicit_ingredient_ids,
		avg_permanent_level=avg_permanent_level,
	)
	if bounds is None:
		return False

	sum_rest_min, sum_rest_max, missing_count = bounds

	# If there are no missing permanents, permanent side is structurally OK;
	# just check usable feasibility below.
	if missing_count == 0:
		return _check_usable_feasibility(
			item_db=item_db,
			recipe=recipe,
			inventory=working_inventory,
			explicit_ingredient_ids=explicit_ingredient_ids,
			ingredient_rarity=ingredient_rarity,
		)

	# Build candidate permanents from remaining inventory.
	candidates = _build_permanent_candidates(
		item_db=item_db,
		inventory=working_inventory if inventory is not None else None,
		explicit_item_ids=explicit_ingredient_ids,
		ingredient_rarity=ingredient_rarity,
	)
	if not candidates:
		return False

	level_to_ids = _build_level_to_ids(
		candidates=candidates,
		inventory=working_inventory if inventory is not None else None,
	)

	level_values: List[int] = [item.required_wave_level for item in candidates]

	# Search over possible missing sums within the structural bounds.
	for target_sum in range(sum_rest_min, sum_rest_max + 1):
		k_solution = find_k_sum_with_reuse(
			nums=level_values,
			k=missing_count,
			target_sum=target_sum,
		)
		if k_solution is None:
			continue

		# If inventory is None, any structural solution is acceptable.
		if inventory is None:
			return True

		# Map level multiset to concrete items under counts.
		assigned_ids = _assign_levels_to_items(k_solution, level_to_ids)
		if assigned_ids is None:
			continue

		# Permanents are feasible; check usables with the same inventory bounds.
		return _check_usable_feasibility(
			item_db=item_db,
			recipe=recipe,
			inventory=working_inventory,
			explicit_ingredient_ids=explicit_ingredient_ids,
			ingredient_rarity=ingredient_rarity,
		)

	return False


def get_feasible_avg_levels_for_recipe(
	target_item_id: int,
	recipe: Recipe,
	item_db: ItemDatabase,
	inventory: Optional[Inventory],
	avg_level_range: Iterable[int],
	explicit_ingredient_ids: Sequence[int],
) -> List[int]:
	"""
	Return the subset of average levels in avg_level_range for which the
	given recipe is feasible under the provided inventory and explicit
	ingredient configuration.
	"""
	feasible_levels: List[int] = []
	for avg_level in avg_level_range:
		if is_avg_level_feasible(
			target_item_id=target_item_id,
			recipe=recipe,
			item_db=item_db,
			inventory=inventory,
			avg_permanent_level=avg_level,
			explicit_ingredient_ids=explicit_ingredient_ids,
		):
			feasible_levels.append(avg_level)
	return feasible_levels


def _check_usable_feasibility(
	item_db: ItemDatabase,
	recipe: Recipe,
	inventory: Optional[Inventory],
	explicit_ingredient_ids: Sequence[int],
	ingredient_rarity: int,
) -> bool:
	if recipe.usable_count <= 0:
		return True

	if inventory is None:
		# Without inventory information, assume usable slots are structurally feasible.
		return True

	explicit_set = {int(x) for x in explicit_ingredient_ids}
	explicit_usable_count = 0

	for item_id in explicit_set:
		item = item_db.items.get(item_id)
		if item is None:
			continue
		if item.is_usable and item.rarity == ingredient_rarity:
			explicit_usable_count += 1

	if explicit_usable_count > recipe.usable_count:
		return False

	missing_usable = recipe.usable_count - explicit_usable_count
	if missing_usable <= 0:
		return True

	available_usable = 0
	for item in item_db.items.values():
		if not item.is_usable:
			continue
		if item.rarity != ingredient_rarity:
			continue
		if item.id in explicit_set:
			continue
		available_usable += inventory.get(item.id, 0)
		if available_usable >= missing_usable:
			return True

	return False


