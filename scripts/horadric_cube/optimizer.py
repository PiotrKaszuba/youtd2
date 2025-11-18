from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
from tqdm import tqdm

from .constants import (
	GAME_PHASE,
	GAME_PHASES,
	GAME_PHASE_VALUE_DICT,
	ITEM_ID,
	ItemValue,
	Inventory,
	USAGE_ITEM_USAGE_CAPS,
)
from .db import ItemDatabase, RecipeDatabase
from .models import Item, Recipe, ResultItemType, Rarity
from .results import HoradricEngine, get_single_result_distribution


@dataclass
class OptimizerConfig:
	recipes_included: Optional[Set[int]] = None
	ingredient_items_excluded: Set[int] = field(default_factory=set)
	ingredient_rarity_whitelist: Optional[Set[int]] = None
	ingredient_level_min: Optional[int] = None
	ingredient_level_max: Optional[int] = None
	num_iterations: int = 50
	learning_rate: float = 0.1
	phases_included: Optional[Set[GAME_PHASE]] = None
	greedy_sets_per_recipe: Dict[int, int] = field(default_factory=dict)
	random_sets_per_recipe: Dict[int, int] = field(default_factory=dict)


def _init_item_values(
	item_db: ItemDatabase,
	usage_values: Dict[ITEM_ID, GAME_PHASE_VALUE_DICT],
) -> Dict[ITEM_ID, ItemValue]:
	item_values: Dict[ITEM_ID, ItemValue] = {}
	for item_id in item_db.items.keys():
		usage = usage_values.get(item_id)
		item_values[item_id] = ItemValue.from_data(
			item_id=item_id,
			usage_value=usage,
		)
	return item_values


def _get_phase_level_bounds(phase: GAME_PHASE) -> Tuple[int, int]:
	"""
	Derive an approximate (lvl_min, lvl_max) range for a given phase index.

	Phases are defined by GAME_PHASES thresholds; the index refers to the
	position in that list.
	"""
	if phase < 0 or phase >= len(GAME_PHASES):
		# Fallback to a wide range if phase index is out of bounds.
		return 0, 1000

	if phase == 0:
		lvl_min = 0
	else:
		prev = GAME_PHASES[phase - 1]
		lvl_min = 0 if not np.isfinite(prev) else int(prev) + 1

	current = GAME_PHASES[phase]
	lvl_max = 1000 if not np.isfinite(current) else int(current)

	return lvl_min, lvl_max


def _build_candidate_pools(
	engine: HoradricEngine,
	config: OptimizerConfig,
	item_values: Dict[ITEM_ID, ItemValue],
	phase: GAME_PHASE,
	state_inventory: Optional[Inventory] = None,
) -> Tuple[List[int], List[int]]:
	permanent_pool: List[int] = []
	usable_pool: List[int] = []

	# Apply static filters (rarity, level, exclusions) via ItemDatabase.filter_items
	filtered_db = engine.item_db.filter_items(
		level_min=config.ingredient_level_min,
		level_max=config.ingredient_level_max,
		rarity_whitelist=config.ingredient_rarity_whitelist,
		remove_item_ids=config.ingredient_items_excluded or set(),
	)

	for item in filtered_db.items.values():

		if state_inventory is not None:
			# Inventory-aware mode: expand pools according to available counts.
			count = state_inventory.get(item.id, 0)
			if count <= 0:
				continue
			if item.is_permanent:
				permanent_pool.extend([item.id] * count)
			elif item.is_usable:
				usable_pool.extend([item.id] * count)
		else:
			# Global mode: single entry per item; duplicates allowed later via
			# sampling with replacement.
			if item.is_permanent:
				permanent_pool.append(item.id)
			elif item.is_usable:
				usable_pool.append(item.id)

	# Sort by current value in this phase to prioritize low-value ingredients.
	permanent_pool.sort(key=lambda i: item_values[i].get_value(phase))
	usable_pool.sort(key=lambda i: item_values[i].get_value(phase))

	return permanent_pool, usable_pool


def _make_value_func(
	item_values: Dict[ITEM_ID, ItemValue],
	phase: GAME_PHASE,
	state_inventory: Optional[Inventory] = None,
):
	"""
	Build a value function V(item_id) for a given phase, optionally applying
	usage caps based on the provided inventory.
	"""

	if state_inventory is None:
		return lambda item_id: item_values[item_id].get_value(phase)

	def V(item_id: ITEM_ID) -> float:
		iv = item_values[item_id]
		u = iv.usage_value.get(phase, 0.0)
		t = iv.transmute_value.get(phase, 0.0)

		# Apply usage caps if configured.
		cap = USAGE_ITEM_USAGE_CAPS.get(item_id)
		if cap is not None:
			max_count, overflow_val = cap
			if state_inventory.get(item_id, 0) >= max_count:
				u = overflow_val

		return max(u, t)

	return V


def generate_candidate_sets_for_recipe(
	engine: HoradricEngine,
	recipe_id: int,
	phase: GAME_PHASE,
	config: OptimizerConfig,
	item_values: Dict[ITEM_ID, ItemValue],
	state_inventory: Optional[Inventory] = None,
) -> List[Sequence[ITEM_ID]]:
	"""
	Generate candidate ingredient sets for a recipe and phase, honoring the
	constraints from OptimizerConfig and optional state inventory.

	This first version keeps the strategy simple:
	- Build pools of permanent and usable items that pass filters.
	- For each recipe, take the cheapest permanents and usables by value.
	- Produce at most one candidate set per recipe for now.
	"""
	recipe: Recipe = engine.recipe_db.recipes[recipe_id]

	if config.recipes_included is not None and recipe_id not in config.recipes_included:
		return []

	# Determine how many greedy and random sets we aim to generate for this recipe.
	greedy_base = config.greedy_sets_per_recipe.get(-1, 0)
	greedy_delta = config.greedy_sets_per_recipe.get(recipe_id, 0)
	target_greedy = max(0, greedy_base + greedy_delta)

	random_base = config.random_sets_per_recipe.get(-1, 0)
	random_delta = config.random_sets_per_recipe.get(recipe_id, 0)
	target_random = max(0, random_base + random_delta)

	if target_greedy <= 0 and target_random <= 0:
		return []

	permanent_pool, usable_pool = _build_candidate_pools(
		engine=engine,
		config=config,
		item_values=item_values,
		phase=phase,
		state_inventory=state_inventory,
	)

	n_perm = recipe.permanent_count
	n_usable = recipe.usable_count

	if n_perm <= 0 and n_usable <= 0:
		return []

	# Not enough items to satisfy counts:
	# - In inventory-aware mode, we require enough copies in the expanded pools.
	# - In global mode, we only require non-empty pools (sampling can reuse items).
	if state_inventory is not None:
		if n_perm > 0 and len(permanent_pool) < n_perm:
			return []
		if n_usable > 0 and len(usable_pool) < n_usable:
			return []
	else:
		if n_perm > 0 and len(permanent_pool) == 0:
			return []
		if n_usable > 0 and len(usable_pool) == 0:
			return []

	candidates: List[Sequence[ITEM_ID]] = []
	seen: Set[Tuple[int, ...]] = set()

	# Greedy sets via sliding window over permanents (or just first usable slice).
	if target_greedy > 0:
		if n_perm > 0:
			max_perm_start = max(0, len(permanent_pool) - n_perm)
			num_perm_sets = max_perm_start + 1
		else:
			max_perm_start = 0
			num_perm_sets = 1

		max_greedy = min(target_greedy, num_perm_sets)

		for i in range(max_greedy):
			current: List[ITEM_ID] = []
			if n_perm > 0:
                # sliding window of size n_perm
				current.extend(permanent_pool[i : i + n_perm])
			if n_usable > 0:
				current.extend(usable_pool[:n_usable])
			if current:
				key = tuple(sorted(current))
				if key not in seen:
					seen.add(key)
					candidates.append(current)

	# Random sets around pools
	if target_random > 0:
		import random

		max_random = target_random
		for _ in range(max_random * 3):  # allow a few retries to avoid duplicates
			current: List[ITEM_ID] = []
			if n_perm > 0:
				if state_inventory is not None:
					# Inventory-aware: sample without replacement from expanded pool
					# to respect available counts.
					if len(permanent_pool) < n_perm:
						break
					current.extend(random.sample(permanent_pool, n_perm))
				else:
					# Global: allow duplicates via sampling with replacement.
					if not permanent_pool:
						break
					current.extend(random.choices(permanent_pool, k=n_perm))
			if n_usable > 0:
				if state_inventory is not None:
					if len(usable_pool) < n_usable:
						break
					current.extend(random.sample(usable_pool, n_usable))
				else:
					if not usable_pool:
						break
					current.extend(random.choices(usable_pool, k=n_usable))
			if not current:
				continue
			key = tuple(sorted(current))
			if key in seen:
				continue
			seen.add(key)
			candidates.append(current)
			if len(candidates) >= target_greedy + target_random:
				break

	return candidates


def _compute_action_value(
	engine: HoradricEngine,
	recipe: Recipe,
	S: Sequence[ITEM_ID],
	phase: GAME_PHASE,
	value_func,
) -> Tuple[float, float]:
	"""
	Compute (expected_result_value, delta) for a single (recipe, S, phase).

	value_func(item_id) should return V[item_id, phase] for the context
	in which this function is called (global iteration or finalized values).
	"""
	# Ingredient opportunity cost under current V.
	ingredient_cost = sum(value_func(i) for i in S)

	# Use actual average permanent level of S, falling back to phase bounds
	# for recipes with no permanents.
	permanent_levels: List[int] = []
	for item_id in S:
		item = engine.item_db.items.get(int(item_id))
		if item is not None and item.is_permanent:
			permanent_levels.append(item.required_wave_level)

	if permanent_levels:
		avg_permanent_level = int(
			sum(permanent_levels) // max(len(permanent_levels), 1)
		)
	else:
		lvl_min, lvl_max = _get_phase_level_bounds(phase)
		avg_permanent_level = (lvl_min + lvl_max) // 2

	# Infer ingredient rarity from the first permanent ingredient if present;
	# otherwise fall back to common.
	ingredient_rarity = Rarity.COMMON
	for item_id in S:
		item = engine.item_db.items.get(int(item_id))
		if item is not None and item.is_permanent:
			ingredient_rarity = item.rarity
			break

	result_rarity = ingredient_rarity + recipe.rarity_change
	if result_rarity < Rarity.COMMON or result_rarity > Rarity.UNIQUE:
		# Invalid rarity – treat as non-profitable.
		return 0.0, -ingredient_cost

	dist = get_single_result_distribution(
		recipe=recipe,
		item_db=engine.item_db,
		avg_permanent_level=avg_permanent_level,
		result_rarity=result_rarity,
		explicit_ingredient_ids=S,
	)

	# Expected value per result slot.
	expected_per_slot = 0.0
	for item_id, prob in dist.items():
		expected_per_slot += prob * value_func(int(item_id))

	expected_result_value = recipe.result_count * expected_per_slot
	delta = expected_result_value - ingredient_cost
	return expected_result_value, delta


def run_value_iteration(
	engine: HoradricEngine,
	usage_values: Dict[ITEM_ID, GAME_PHASE_VALUE_DICT],
	config: OptimizerConfig,
) -> Dict[ITEM_ID, ItemValue]:
	"""
	Global value iteration to learn absolute transmute values T[i, phase].

	This is inventory-agnostic but respects OptimizerConfig constraints on
	recipes and ingredients.
	"""
	item_values = _init_item_values(engine.item_db, usage_values)

	# Extract U and T tables for iterative updates.
	U: Dict[ITEM_ID, Dict[GAME_PHASE, float]] = {}
	T: Dict[ITEM_ID, Dict[GAME_PHASE, float]] = {}

	num_phases = len(GAME_PHASES)

	for item_id, iv in item_values.items():
		U[item_id] = dict(iv.usage_value)
		T[item_id] = {phase_idx: 0.0 for phase_idx in range(num_phases)}

	return _run_value_iteration_core(
		engine=engine,
		item_values=item_values,
		U=U,
		T=T,
		config=config,
		num_iterations=config.num_iterations,
		state_inventory=None,
		state_recipes_available=None,
	)


def _run_value_iteration_core(
	engine: HoradricEngine,
	item_values: Dict[ITEM_ID, ItemValue],
	U: Dict[ITEM_ID, Dict[GAME_PHASE, float]],
	T: Dict[ITEM_ID, Dict[GAME_PHASE, float]],
	config: OptimizerConfig,
	num_iterations: int,
	state_inventory: Optional[Inventory],
	state_recipes_available: Optional[Set[int]],
) -> Dict[ITEM_ID, ItemValue]:
	"""
	Shared core for global and state-local value iteration.

	- item_values: base ItemValue map (used for structure and initial values).
	- U/T: usage and transmute tables to be updated in-place.
	- num_iterations: number of sweeps over all configured phases.
	- state_inventory / state_recipes_available: restrict actions in state-local mode.
	"""
	alpha = config.learning_rate
	phase_indices = config.phases_included if config.phases_included is not None else range(len(GAME_PHASES))

	for _ in tqdm(range(num_iterations)):
		for phase in phase_indices:
			def V(item_id: ITEM_ID) -> float:
				return max(U[item_id].get(phase, 0.0), T[item_id].get(phase, 0.0))

			# Per-item best candidate value in this phase.
			# For global optimization we seed from current T so values are
			# monotone non-decreasing. For state-local refinement we allow T
			# to decrease, so we seed from 0.0 each iteration.
			if state_inventory is None and state_recipes_available is None:
				best_candidate_value: Dict[ITEM_ID, float] = {
					item_id: T[item_id].get(phase, 0.0) for item_id in item_values.keys()
				}
			else:
				best_candidate_value = {item_id: 0.0 for item_id in item_values.keys()}

			for recipe in engine.recipe_db.recipes.values():
				recipe_id = recipe.id

				if state_recipes_available is not None and recipe_id not in state_recipes_available:
					continue
				if config.recipes_included is not None and recipe_id not in config.recipes_included:
					continue

				candidate_sets = generate_candidate_sets_for_recipe(
					engine=engine,
					recipe_id=recipe_id,
					phase=phase,
					config=config,
					item_values=item_values,
					state_inventory=state_inventory,
				)
				for S in candidate_sets:
					if not S:
						continue

					expected_result_value, _ = _compute_action_value(
						engine=engine,
						recipe=recipe,
						S=S,
						phase=phase,
						value_func=V,
					)

					per_item_candidate = expected_result_value / float(len(S))

					for item_id in S:
						current_best = best_candidate_value.get(item_id, 0.0)
						if per_item_candidate > current_best:
							best_candidate_value[item_id] = per_item_candidate

			# Soft-max update for T in this phase.
			for item_id in item_values.keys():
				old_t = T[item_id].get(phase, 0.0)
				target = best_candidate_value.get(item_id, old_t)
				T[item_id][phase] = (1.0 - alpha) * old_t + alpha * target

	# Build final ItemValue objects with learned T.
	final_item_values: Dict[ITEM_ID, ItemValue] = {}
	for item_id, iv in item_values.items():
		transmute_value: GAME_PHASE_VALUE_DICT = {}
		for phase_idx in range(len(GAME_PHASES)):
			transmute_value[phase_idx] = T[item_id].get(phase_idx, 0.0)
		final_item_values[item_id] = ItemValue(
			item_id=item_id,
			usage_value=U[item_id],
			transmute_value=transmute_value,
		)

	return final_item_values


def run_state_local_refinement(
	engine: HoradricEngine,
	global_item_values: Dict[ITEM_ID, ItemValue],
	state_inventory: Inventory,
	state_recipes_available: Optional[Set[int]],
	config: OptimizerConfig,
	extra_iterations: int = 10,
	new_usage_values: Optional[Dict[ITEM_ID, GAME_PHASE_VALUE_DICT]] = None,
) -> Dict[ITEM_ID, ItemValue]:
	"""
	Refine T/V for a specific state, using global_item_values as initialization.

	This runs a smaller number of iterations, restricted to actions that are
	feasible under the provided inventory and available recipes.
	"""
	item_values = global_item_values

	U: Dict[ITEM_ID, Dict[GAME_PHASE, float]] = {}
	T: Dict[ITEM_ID, Dict[GAME_PHASE, float]] = {}

	for item_id, iv in item_values.items():
		U[item_id] = dict(iv.usage_value)
		T[item_id] = dict(iv.transmute_value)

	# Optionally overlay new usage values for this state.
	if new_usage_values is not None:
		for item_id, usage_dict in new_usage_values.items():
			if item_id not in U:
				continue
			iv_override = ItemValue.from_data(
				item_id=item_id,
				usage_value=dict(usage_dict),
				inventory=state_inventory,
				usage_caps=USAGE_ITEM_USAGE_CAPS,
			)
			U[item_id] = dict(iv_override.usage_value)

	return _run_value_iteration_core(
		engine=engine,
		item_values=item_values,
		U=U,
		T=T,
		config=config,
		num_iterations=extra_iterations,
		state_inventory=state_inventory,
		state_recipes_available=state_recipes_available,
	)


def rank_items_by_transmute_gain(
	item_values: Dict[ITEM_ID, ItemValue],
	phase: GAME_PHASE,
	top_n: int = 20,
) -> List[Tuple[ITEM_ID, float]]:
	results: List[Tuple[ITEM_ID, float]] = []
	for item_id, iv in item_values.items():
		u = iv.usage_value.get(phase, 0.0)
		t = iv.transmute_value.get(phase, 0.0)
		gain = t - u
		results.append((item_id, gain))
	results.sort(key=lambda x: x[1], reverse=True)
	return results[:top_n]


def rank_recipes_by_net_gain(
	engine: HoradricEngine,
	item_values: Dict[ITEM_ID, ItemValue],
	phase: GAME_PHASE,
	config: OptimizerConfig,
	state_inventory: Optional[Inventory] = None,
) -> List[Tuple[int, Sequence[ITEM_ID], float]]:
	results: List[Tuple[int, Sequence[ITEM_ID], float]] = []

	value_func = _make_value_func(
		item_values=item_values,
		phase=phase,
		state_inventory=state_inventory,
	)

	for recipe in engine.recipe_db.recipes.values():
		recipe_id = recipe.id
		if config.recipes_included is not None and recipe_id not in config.recipes_included:
			continue

		candidate_sets = generate_candidate_sets_for_recipe(
			engine=engine,
			recipe_id=recipe_id,
			phase=phase,
			config=config,
			item_values=item_values,
			state_inventory=state_inventory,
		)
		for S in candidate_sets:
			if not S:
				continue
			_, delta = _compute_action_value(
				engine=engine,
				recipe=recipe,
				S=S,
				phase=phase,
				value_func=value_func,
			)
			if delta > 0.0:
				results.append((recipe_id, S, delta))

	results.sort(key=lambda x: x[2], reverse=True)
	return results


def choose_best_transmute_action(
	engine: HoradricEngine,
	item_values: Dict[ITEM_ID, ItemValue],
	state_inventory: Inventory,
	state_recipes_available: Optional[Set[int]],
	phase: GAME_PHASE,
	config: OptimizerConfig,
) -> Optional[Tuple[int, Sequence[ITEM_ID], float]]:
	"""
	Recommend the best transmute action for a given state, or None if no
	positive-value action exists.
	"""
	actions = list_transmute_actions_for_state(
		engine=engine,
		item_values=item_values,
		state_inventory=state_inventory,
		state_recipes_available=state_recipes_available,
		phase=phase,
		config=config,
		min_delta=0.0,
	)
	if not actions:
		return None
	return actions[0]


def list_transmute_actions_for_state(
	engine: HoradricEngine,
	item_values: Dict[ITEM_ID, ItemValue],
	state_inventory: Inventory,
	state_recipes_available: Optional[Set[int]],
	phase: GAME_PHASE,
	config: OptimizerConfig,
	min_delta: float = float("-inf"),
) -> List[Tuple[int, Sequence[ITEM_ID], float]]:
	"""
	Enumerate and rank all candidate transmute actions for a given state.

	Returns a list of (recipe_id, ingredient_ids, delta) sorted by descending
	delta. min_delta can be used to filter out obviously bad actions.
	"""
	actions: List[Tuple[int, Sequence[ITEM_ID], float]] = []

	value_func = _make_value_func(
		item_values=item_values,
		phase=phase,
		state_inventory=state_inventory,
	)

	for recipe in engine.recipe_db.recipes.values():
		recipe_id = recipe.id
		if state_recipes_available is not None and recipe_id not in state_recipes_available:
			continue
		if config.recipes_included is not None and recipe_id not in config.recipes_included:
			continue

		candidate_sets = generate_candidate_sets_for_recipe(
			engine=engine,
			recipe_id=recipe_id,
			phase=phase,
			config=config,
			item_values=item_values,
			state_inventory=state_inventory,
		)

		for S in candidate_sets:
			if not S:
				continue
			_, delta = _compute_action_value(
				engine=engine,
				recipe=recipe,
				S=S,
				phase=phase,
				value_func=value_func,
			)
			if delta >= min_delta:
				actions.append((recipe_id, S, delta))

	actions.sort(key=lambda x: x[2], reverse=True)
	return actions


__all__ = [
	"OptimizerConfig",
	"run_value_iteration",
	"run_state_local_refinement",
	"rank_items_by_transmute_gain",
	"rank_recipes_by_net_gain",
	"choose_best_transmute_action",
	"list_transmute_actions_for_state",
]


