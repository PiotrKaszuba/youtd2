from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
from tqdm import tqdm

from .constants import (
	GAME_PHASE,
	GAME_PHASES,
	GAME_PHASE_VALUE_DICT,
	ITEM_ID,
	ItemValue,
	Inventory,
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
	ingredient_include_permanent: bool = True
	ingredient_include_usable: bool = True
	num_iterations: int = 50
	learning_rate: float = 0.1
	phases_included: Optional[Set[GAME_PHASE]] = None
	greedy_sets_per_recipe: Dict[int, int] = field(default_factory=dict)
	random_sets_per_recipe: Dict[int, int] = field(default_factory=dict)
	# Multi-strategy controls
	strategies: List[str] = field(default_factory=lambda: ["max", "avg", "percentile", "custom"])
	output_strategy: str = "custom"
	percentile_target: float = 85.0
	custom_strategy_weights: Dict[str, float] = field(default_factory=dict)
	# Constraints: skip (recipe_id, ingredient_rarity) pairs
	excluded_recipe_rarities: Set[Tuple[int, int]] = field(default_factory=set)


# ---------- Strategy Interfaces ----------

class ValueStrategy:
	def name(self) -> str:
		return "base"

	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		# Default safe behavior: keep current value if no candidates
		if not candidate_values:
			return current_value
		return max(candidate_values)


class MaxStrategy(ValueStrategy):
	def name(self) -> str:
		return "max"

	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		return max(candidate_values) if candidate_values else current_value


class AvgStrategy(ValueStrategy):
	def name(self) -> str:
		return "avg"

	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		return float(sum(candidate_values)) / float(max(len(candidate_values), 1)) if candidate_values else current_value


class PercentileStrategy(ValueStrategy):
	def __init__(self, percentile: float) -> None:
		self._p = max(0.0, min(100.0, float(percentile)))

	def name(self) -> str:
		return "percentile"

	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		if not candidate_values:
			return current_value
		try:
			return float(np.percentile(np.array(candidate_values, dtype=float), self._p))
		except Exception:
			values = sorted(candidate_values)
			if not values:
				return current_value
			idx = int(round((self._p / 100.0) * (len(values) - 1)))
			return float(values[idx])


class CustomStrategy(ValueStrategy):
	def __init__(self, percentile: float, custom_strategy_weights: Dict[str, float]) -> None:
		self._max = MaxStrategy()
		self._avg = AvgStrategy()
		self._pct = PercentileStrategy(percentile)
		self._custom_strategy_weights = custom_strategy_weights

	def name(self) -> str:
		return "custom"

	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		if not candidate_values:
			return current_value
		weights = self._custom_strategy_weights
		if not weights:
			weights = {
				"max": 1.0,
				"avg": 1.0,
				"pct": 1.0,
			}
		
		if "max" in weights and weights["max"] != 0.0:
			max_v = weights["max"] * self._max.calculate_next_value(current_value, candidate_values)
		else:
			max_v = 0.0
		if "avg" in weights and weights["avg"] != 0.0:
			avg_v = weights["avg"] * self._avg.calculate_next_value(current_value, candidate_values)
		else:
			avg_v = 0.0
		if "pct" in weights and weights["pct"] != 0.0:
			pct_v = weights["pct"] * self._pct.calculate_next_value(current_value, candidate_values)
		else:
			pct_v = 0.0
		return (max_v + avg_v + pct_v) / float(max(len(weights.values()), 1))


def _init_item_values(
	item_db: ItemDatabase,
	usage_values: Dict[ITEM_ID, Any],
) -> Dict[ITEM_ID, ItemValue]:
	item_values: Dict[ITEM_ID, ItemValue] = {}
	for item_id in item_db.items.keys():
		usage_entry = usage_values.get(item_id)
		usage_val = None
		usage_cap = None
		family_info = None

		if isinstance(usage_entry, tuple):
			if len(usage_entry) == 3:
				usage_val, usage_cap, family_info = usage_entry
			elif len(usage_entry) == 2:
				usage_val, usage_cap = usage_entry
		elif isinstance(usage_entry, dict):
			usage_val = usage_entry

		item_values[item_id] = ItemValue.from_data(
			item_id=item_id,
			usage_value=usage_val,
			usage_cap_single=usage_cap,
			family_info=family_info,
		)
	return item_values

def _update_item_values(
	item_values: Dict[ITEM_ID, ItemValue],
	usage_values: Dict[ITEM_ID, Any],
	inventory: Optional[Inventory] = None,
) -> Dict[ITEM_ID, ItemValue]:
	item_values_new: Dict[ITEM_ID, ItemValue] = {}
	for item_id, iv in item_values.items():
		usage_entry = usage_values.get(item_id)
		usage_val = None
		usage_cap = None
		family_info = None
		
		if isinstance(usage_entry, tuple):
			if len(usage_entry) == 3:
				usage_val, usage_cap, family_info = usage_entry
			elif len(usage_entry) == 2:
				usage_val, usage_cap = usage_entry
		elif isinstance(usage_entry, dict):
			usage_val = usage_entry
			
		item_values_new[item_id] = iv.update_keep_transmute_value(usage_val, inventory, usage_cap_single=usage_cap, family_info=family_info)
	return item_values_new


def _build_candidate_pools(
	engine: HoradricEngine,
	config: OptimizerConfig,
	state_inventory: Optional[Inventory] = None,
	value_func: Optional[Any] = None,
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
	if value_func is not None:
		# Use consume_count=1 for initial sorting to reflect "cost of using one" approximately
		permanent_pool.sort(key=lambda i: float(value_func(i, consume_count=1)))
		usable_pool.sort(key=lambda i: float(value_func(i, consume_count=1)))

	return permanent_pool, usable_pool


# ---------- Candidate Generation (rarity-aware, budgeted) ----------

@dataclass
class CandidateSet:
	recipe_id: int
	ingredients: List[int]


@dataclass
class CachedCandidate:
	recipe_id: int
	ingredients: Tuple[int, ...]
	result_rarity: int
	avg_permanent_level: int
	result_distribution: Dict[int, float]


def _make_value_func(
	item_values: Dict[ITEM_ID, ItemValue],
	phase: GAME_PHASE,
	state_inventory: Optional[Inventory] = None,
):
	"""
	Build a value function V(item_id, consume_count=0) for a given phase, optionally applying
	usage caps based on the provided inventory.
	"""

	if state_inventory is None:
		return lambda item_id, consume_count=0: item_values[item_id].get_value(phase)

	def V(item_id: ITEM_ID, consume_count: int = 0) -> float:
		iv = item_values[item_id]
		# Calculate effective usage value considering inventory state
		# Re-use logic from ItemValue.determine_usage_value but simplified for single lookup
		
		base_u = iv.usage_value.get(phase, 0.0)
		t = iv.transmute_value.get(phase, 0.0)

		if iv.usage_cap is None:
			return max(base_u, t)

		# If we have usage caps, we need to check effective count
		# effective_count = (current_inventory - consume_count) + shadow_count
		
		# 1. Current Inventory
		count = state_inventory.get(item_id, 0)
		
		# 2. Shadow Count
		shadow_count = 0.0
		if iv.family_info:
			from .constants import FAMILY_RULES, get_item_family_info # Local import to avoid circular dependency if any
			fam_id, tier, _ = iv.family_info
			
			for other_id, other_count in state_inventory.items():
				if other_count <= 0:
					continue
				# Optimization: we could pre-calculate this map, but for now iteration is fine
				other_fam_info = get_item_family_info(other_id)
				if not other_fam_info:
					continue
				other_fam_id, other_tier, _ = other_fam_info
				
				if other_fam_id == fam_id and other_tier > tier:
					tier_diff = other_tier - tier
					rule = FAMILY_RULES.get(fam_id)
					if rule and tier_diff in rule.downward_impacts:
						impact_dict = rule.downward_impacts[tier_diff]
						base_impact = impact_dict.get(-1, 0.0)
						impact = base_impact + impact_dict.get(phase, 0.0)
						shadow_count += other_count * impact

		effective_count = max(0, count - consume_count) + shadow_count
		max_count, overflow_val = iv.usage_cap
		
		u = base_u
		if effective_count >= max_count:
			u = overflow_val

		return max(u, t)

	return V


def _distribute_budgets_by_rarity(
	engine: HoradricEngine,
	permanent_pool: List[int],
	n_perm: int,
	target_greedy: int,
	target_random: int,
	state_inventory: Optional[Inventory],
	recipe_id: int,
	config: OptimizerConfig,
) -> List[Tuple[List[int], int, int]]:
	"""
	Group permanent items by rarity and distribute greedy/random budgets proportionally
	across valid rarities (respecting excluded pairs and inventory sufficiency).
	Returns a list of (perm_sub_pool, greedy_budget, random_budget).
	"""
	if n_perm <= 0:
		# Only usables: a single batch with the entire budget and empty perm pool
		return [([], target_greedy, target_random)]

	pools_by_rarity: Dict[int, List[int]] = defaultdict(list)
	for pid in permanent_pool:
		item = engine.item_db.items.get(int(pid))
		if item:
			pools_by_rarity[item.rarity].append(pid)

	# Valid rarities: enough items and not excluded by config
	valid_rarities: List[int] = []
	total_items_count = 0
	for rarity, pool in pools_by_rarity.items():
		if state_inventory is not None and len(pool) < n_perm:
			continue
		if not pool:
			continue
		if (recipe_id, rarity) in (config.excluded_recipe_rarities or set()):
			continue
		valid_rarities.append(rarity)
		total_items_count += len(pool)

	if total_items_count <= 0:
		return []

	valid_rarities.sort()
	results: List[Tuple[List[int], int, int]] = []
	current_g = 0
	current_r = 0
	cumulative_items = 0
	for rarity in valid_rarities:
		pool = pools_by_rarity[rarity]
		cumulative_items += len(pool)

		target_g_cum = int(target_greedy * cumulative_items / total_items_count)
		g_budget = target_g_cum - current_g
		current_g = target_g_cum

		target_r_cum = int(target_random * cumulative_items / total_items_count)
		r_budget = target_r_cum - current_r
		current_r = target_r_cum

		results.append((pool, g_budget, r_budget))

	return results


def generate_greedy_sets_for_recipe(
	engine: HoradricEngine,
	recipe_id: int,
	config: OptimizerConfig,
	state_inventory: Optional[Inventory] = None,
	value_func: Optional[Any] = None,
) -> List[Sequence[ITEM_ID]]:
	recipe: Recipe = engine.recipe_db.recipes[recipe_id]
	permanent_pool, usable_pool = _build_candidate_pools(
		engine=engine,
		config=config,
		state_inventory=state_inventory,
		value_func=value_func,
	)
	n_perm = recipe.permanent_count
	n_usable = recipe.usable_count

	greedy_base = config.greedy_sets_per_recipe.get(-1, 0)
	greedy_delta = config.greedy_sets_per_recipe.get(recipe_id, 0)
	target_greedy = max(0, greedy_base + greedy_delta)
	if target_greedy <= 0:
		return []

	# basic feasibility checks
	if n_perm <= 0 and n_usable <= 0:
		return []
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

	batches = _distribute_budgets_by_rarity(
		engine=engine,
		permanent_pool=permanent_pool,
		n_perm=n_perm,
		target_greedy=target_greedy,
		target_random=0,
		state_inventory=state_inventory,
		recipe_id=recipe_id,
		config=config,
	)
	if not batches:
		return []

	candidates: List[Sequence[ITEM_ID]] = []
	seen: Set[Tuple[int, ...]] = set()
	for perm_sub_pool, g_budget, _ in batches:
		if g_budget <= 0:
			continue
		# Sliding window over sorted rarity pool
		num_perm_sets = 1 if n_perm == 0 else max(0, len(perm_sub_pool) - n_perm) + 1
		iters = min(g_budget, num_perm_sets)
		for i in range(iters):
			current: List[ITEM_ID] = []
			if n_perm > 0:
				current.extend(perm_sub_pool[i : i + n_perm])
			if n_usable > 0:
				current.extend(usable_pool[:n_usable])
			if not current:
				continue
			key = tuple(sorted(current))
			if key in seen:
				continue
			seen.add(key)
			candidates.append(list(key))
	return candidates


def generate_random_sets_for_recipe(
	engine: HoradricEngine,
	recipe_id: int,
	config: OptimizerConfig,
	state_inventory: Optional[Inventory] = None,
) -> List[Sequence[ITEM_ID]]:
	# Prefer the authoritative recipe_db
	recipe = engine.recipe_db.recipes[recipe_id]

	permanent_pool, usable_pool = _build_candidate_pools(
		engine=engine,
		config=config,
		state_inventory=state_inventory,
	)
	n_perm = recipe.permanent_count
	n_usable = recipe.usable_count

	random_base = config.random_sets_per_recipe.get(-1, 0)
	random_delta = config.random_sets_per_recipe.get(recipe_id, 0)
	target_random = max(0, random_base + random_delta)
	if target_random <= 0:
		return []

	if n_perm <= 0 and n_usable <= 0:
		return []
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

	batches = _distribute_budgets_by_rarity(
		engine=engine,
		permanent_pool=permanent_pool,
		n_perm=n_perm,
		target_greedy=0,
		target_random=target_random,
		state_inventory=state_inventory,
		recipe_id=recipe_id,
		config=config,
	)
	if not batches:
		return []

	import random
	candidates: List[Sequence[ITEM_ID]] = []
	seen: Set[Tuple[int, ...]] = set()
	for perm_sub_pool, _, r_budget in batches:
		if r_budget <= 0:
			continue
		tries = max(r_budget * 4, r_budget)
		for _ in range(tries):
			current: List[ITEM_ID] = []
			if n_perm > 0:
				if state_inventory is not None:
					if len(perm_sub_pool) < n_perm:
						continue
					current.extend(random.sample(perm_sub_pool, n_perm))
				else:
					current.extend(random.choices(perm_sub_pool, k=n_perm))
			if n_usable > 0:
				if state_inventory is not None:
					if len(usable_pool) < n_usable:
						continue
					current.extend(random.sample(usable_pool, n_usable))
				else:
					if not usable_pool:
						continue
					current.extend(random.choices(usable_pool, k=n_usable))
			if not current:
				continue
			key = tuple(sorted(current))
			if key in seen:
				continue
			seen.add(key)
			candidates.append(list(key))
			if len(candidates) >= r_budget:
				break
	return candidates

def generate_candidate_sets_for_recipe(
	engine: HoradricEngine,
	recipe_id: int,
	phase: GAME_PHASE,
	config: OptimizerConfig,
	item_values: Dict[ITEM_ID, ItemValue],
	state_inventory: Optional[Inventory] = None,
	value_func: Optional[Any] = None,
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

	greedy = generate_greedy_sets_for_recipe(
		engine=engine,
		recipe_id=recipe_id,
		config=config,
		state_inventory=state_inventory,
		value_func=value_func,
	)
	randoms = generate_random_sets_for_recipe(
		engine=engine,
		recipe_id=recipe_id,
		config=config,
		state_inventory=state_inventory,
	)
	# Merge and de-dup
	seen: Set[Tuple[int, ...]] = set()
	out: List[Sequence[ITEM_ID]] = []
	for lst in (greedy, randoms):
		for S in lst:
			key = tuple(sorted(S))
			if key in seen:
				continue
			seen.add(key)
			out.append(list(key))
	return out


def _compute_action_value(
	engine: HoradricEngine,
	recipe: Recipe,
	S: Sequence[ITEM_ID],
	phase: GAME_PHASE,
	value_func,
	avg_per_ingredient: bool = False,
) -> Tuple[float, float]:
	"""
	Compute (expected_result_value, delta) for a single (recipe, S, phase).

	value_func(item_id) should return V[item_id, phase] for the context
	in which this function is called (global iteration or finalized values).
	"""
	# Ingredient opportunity cost under current V.
	# Count occurrences of each item to correctly apply consume_count
	item_counts = defaultdict(int)
	ingredient_cost = 0.0
	
	for i in S:
		item_counts[i] += 1
		# Pass consume_count = current count (before this usage, so 1-based index of usage)
		# value_func(i, consume_count=1) calculates value of 1st item consumed
		# value_func(i, consume_count=2) calculates value of 2nd item consumed
		# Wait, implementation of value_func uses (count - consume_count).
		# If I have 2 items. Cap is 2.
		# Cost of 1st item: V(i, 1). effective = 2 - 1 = 1. Usage Val = Full. Correct?
		# If effective < Cap (1 < 2), value is Full.
		# This means "The item remaining (1st one) has full value".
		# The cost should be "The value of the item REMOVED".
		# If I remove the 2nd item (going from 2 to 1). The item REMOVED was the 2nd one.
		# Its marginal contribution was shifting state from 1 -> 2.
		# V(i, 0) is value of adding one at state 0.
		# V(i, 1) is value of adding one at state 1.
		# If we are at state 2. We consume one. We go to state 1.
		# The lost value is V(i, 1) (Value of going 1->2).
		# So cost of 1st ingredient = V(i, 1).
		# Cost of 2nd ingredient (if we use 2) = V(i, 2) (Value of going 0->1).
		# My implementation of V(i, consume) calculates value of adding NEXT item starting from (inventory - consume).
		# So V(i, 1) -> effective = count - 1. Value of adding (count)th item. Correct.
		ingredient_cost += value_func(i, consume_count=item_counts[i])

	# Use actual average permanent level of S, falling back to phase bounds
	# for recipes with no permanents.
	permanent_levels: List[int] = []
	for item_id in S:
		item = engine.item_db.items.get(int(item_id))
		if item is not None and item.is_permanent:
			permanent_levels.append(item.required_wave_level)


	avg_permanent_level = int(
		sum(permanent_levels) // max(len(permanent_levels), 1)
	)

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
	if avg_per_ingredient:
		expected_result_value = expected_result_value / float(max(len(S), 1))
		delta = delta / float(max(len(S), 1))
	return expected_result_value, delta


def run_value_iteration(
	engine: HoradricEngine,
	usage_values: Dict[ITEM_ID, Any],
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
	T_tables: Dict[str, Dict[ITEM_ID, Dict[GAME_PHASE, float]]] = {}
	strategies: List[ValueStrategy] = []

	num_phases = len(GAME_PHASES)

	for item_id, iv in item_values.items():
		U[item_id] = dict(iv.usage_value)
	# Build strategies
	strategy_names = list(dict.fromkeys(config.strategies or ["max", "avg", "percentile", "custom"]))
	for s in strategy_names:
		if s == "max":
			strategies.append(MaxStrategy())
		elif s == "avg":
			strategies.append(AvgStrategy())
		elif s == "percentile":
			strategies.append(PercentileStrategy(config.percentile_target))
		elif s == "custom":
			strategies.append(CustomStrategy(config.percentile_target, config.custom_strategy_weights))
		else:
			strategies.append(MaxStrategy())
	for strat in strategies:
		T_tables[strat.name()] = {item_id: {phase_idx: 0.0 for phase_idx in range(num_phases)} for item_id in item_values.keys()}

	return _run_value_iteration_core(
		engine=engine,
		item_values=item_values,
		U=U,
		T_tables=T_tables,
		strategies=strategies,
		config=config,
		num_iterations=config.num_iterations,
		state_inventory=None,
		state_recipes_available=None,
	)


def _run_value_iteration_core(
	engine: HoradricEngine,
	item_values: Dict[ITEM_ID, ItemValue],
	U: Dict[ITEM_ID, Dict[GAME_PHASE, float]],
	T_tables: Dict[str, Dict[ITEM_ID, Dict[GAME_PHASE, float]]],
	strategies: List[ValueStrategy],
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

	# Precompute random candidate cache once for all recipes
	random_cache: Dict[int, List[CachedCandidate]] = {}
	for recipe in engine.recipe_db.recipes.values():
		recipe_id = recipe.id
		if state_recipes_available is not None and recipe_id not in state_recipes_available:
			continue
		if config.recipes_included is not None and recipe_id not in config.recipes_included:
			continue
		random_sets = generate_random_sets_for_recipe(
			engine=engine,
			recipe_id=recipe_id,
			config=config,
			state_inventory=state_inventory,
		)

		print(f"Random sets for recipe {recipe_id}: {len(random_sets)}")

		cached_list: List[CachedCandidate] = []
		for S in random_sets:
			if not S:
				continue
			permanent_levels: List[int] = []
			ingredient_rarity = Rarity.COMMON
			for item_id in S:
				item = engine.item_db.items.get(int(item_id))
				if item is not None and item.is_permanent:
					permanent_levels.append(item.required_wave_level)
					ingredient_rarity = item.rarity
			
			avg_permanent_level = int(sum(permanent_levels) // max(len(permanent_levels), 1))
			
			result_rarity = ingredient_rarity + recipe.rarity_change
			if result_rarity < Rarity.COMMON or result_rarity > Rarity.UNIQUE:
				continue
			dist = get_single_result_distribution(
				recipe=recipe,
				item_db=engine.item_db,
				avg_permanent_level=avg_permanent_level,
				result_rarity=result_rarity,
				explicit_ingredient_ids=S,
			)
			cached_list.append(CachedCandidate(
				recipe_id=recipe_id,
				ingredients=tuple(sorted(S)),
				result_rarity=result_rarity,
				avg_permanent_level=avg_permanent_level,
				result_distribution=dist,
			))
		random_cache[recipe_id] = cached_list

	for _ in tqdm(range(num_iterations)):
		greedy_cached_by_phase_and_recipe: Dict[int, Dict[int, List[CachedCandidate]]] = {}
		for phase in phase_indices:			
			greedy_cached_by_phase_and_recipe[phase] = {}
			for recipe in engine.recipe_db.recipes.values():
				recipe_id = recipe.id
				if state_recipes_available is not None and recipe_id not in state_recipes_available:
					continue
				if config.recipes_included is not None and recipe_id not in config.recipes_included:
					continue
				greedy_sets = generate_greedy_sets_for_recipe(
					engine=engine,
					recipe_id=recipe_id,
					config=config,
					state_inventory=state_inventory,
					value_func=lambda i, consume_count=0, T_tables=T_tables, U=U, phase=phase, config=config: max(
						U[i].get(phase, 0.0),
						T_tables.get(config.output_strategy or "custom", {}).get(i, {}).get(phase, 0.0),
					),
				)
				cached_list: List[CachedCandidate] = []
				greedy_cached_by_phase_and_recipe[phase][recipe_id] = cached_list
				for S in greedy_sets:
					if not S:
						continue
					permanent_levels: List[int] = []
					ingredient_rarity = None
					for item_id in S:
						item = engine.item_db.items.get(int(item_id))
						assert item is not None and item.is_permanent and (ingredient_rarity is None or item.rarity == ingredient_rarity)
						permanent_levels.append(item.required_wave_level)
						ingredient_rarity = item.rarity
					
					avg_permanent_level = int(sum(permanent_levels) // max(len(permanent_levels), 1))
					result_rarity = ingredient_rarity + recipe.rarity_change
					if result_rarity < Rarity.COMMON or result_rarity > Rarity.UNIQUE:
						continue
					dist = get_single_result_distribution(
						recipe=recipe,
						item_db=engine.item_db,
						avg_permanent_level=avg_permanent_level,
						result_rarity=result_rarity,
						explicit_ingredient_ids=S,
					)
					cached_list.append(CachedCandidate(
						recipe_id=recipe_id,
						ingredients=tuple(sorted(S)),
						result_rarity=result_rarity,
						avg_permanent_level=avg_permanent_level,
						result_distribution=dist,
					))

		# Evaluate per strategy
		for strategy in strategies:
			T = T_tables[strategy.name()]

			def V(item_id: ITEM_ID, phase: GAME_PHASE) -> float:
				return max(U[item_id].get(phase, 0.0), T[item_id].get(phase, 0.0))

			candidate_values_by_phase_and_item: Dict[int, Dict[ITEM_ID, List[float]]] = {phase: {item_id: [] for item_id in item_values.keys()} for phase in phase_indices}

			# Random cached
			for recipe_id, cc_list in random_cache.items():
				recipe = engine.recipe_db.recipes[recipe_id]
				result_count = recipe.result_count
				for cc in cc_list:
					S = list(cc.ingredients)
					if not S:
						continue
					expected_per_slot_per_phase: Dict[int, float] = {phase: 0.0 for phase in phase_indices}
					for out_id, prob in cc.result_distribution.items():
						for phase in phase_indices:
							expected_per_slot_per_phase[phase] += prob * V(int(out_id), phase)
					
					expected_result_value_per_phase: Dict[int, float] = {phase: result_count * expected_per_slot_per_phase[phase] for phase in phase_indices}
					per_item_candidate_per_phase: Dict[int, float] = {phase: expected_result_value_per_phase[phase] / float(max(len(S), 1)) for phase in phase_indices}
					for i in S:
						for phase in phase_indices:
							candidate_values_by_phase_and_item[phase][i].append(per_item_candidate_per_phase[phase])

			# Greedy cached
			for phase in phase_indices:
				for recipe_id, cc_list in greedy_cached_by_phase_and_recipe[phase].items():
					recipe = engine.recipe_db.recipes[recipe_id]
					result_count = recipe.result_count
					for cc in cc_list:
						S = list(cc.ingredients)
						if not S:
							continue
						expected_per_slot = 0.0
						for out_id, prob in cc.result_distribution.items():
							expected_per_slot += prob * V(int(out_id), phase)
						expected_result_value = result_count * expected_per_slot
						per_item_candidate = expected_result_value / float(max(len(S), 1))
						for i in S:
							candidate_values_by_phase_and_item[phase][i].append(per_item_candidate)

			# Soft update per item
			for ph in phase_indices:
				for item_id in item_values.keys():
					old_t = T[item_id].get(ph, 0.0)
					candidates = candidate_values_by_phase_and_item[ph].get(item_id, [])
					target = strategy.calculate_next_value(old_t, candidates)
					T[item_id][ph] = (1.0 - alpha) * old_t + alpha * target
			T_tables[strategy.name()] = T

	# Build final ItemValue objects with learned T.
	final_item_values: Dict[ITEM_ID, ItemValue] = {}
	# Select output face strategy
	output_strategy = config.output_strategy or "custom"
	if output_strategy not in T_tables:
		output_strategy = next(iter(T_tables.keys()))
	for item_id, iv in item_values.items():
		face: GAME_PHASE_VALUE_DICT = {}
		for phase_idx in range(len(GAME_PHASES)):
			face[phase_idx] = T_tables[output_strategy][item_id].get(phase_idx, 0.0)
		all_tables: Dict[str, GAME_PHASE_VALUE_DICT] = {}
		for name, table in T_tables.items():
			all_tables[name] = {phase_idx: table[item_id].get(phase_idx, 0.0) for phase_idx in range(len(GAME_PHASES))}
		final_item_values[item_id] = ItemValue(
			item_id=item_id,
			usage_value=U[item_id],
			transmute_value=face,
			transmute_values_by_strategy=all_tables,
			usage_cap=iv.usage_cap,
		)

	return final_item_values


def run_state_local_refinement(
	engine: HoradricEngine,
	global_item_values: Dict[ITEM_ID, ItemValue],
	state_inventory: Inventory,
	state_recipes_available: Optional[Set[int]],
	config: OptimizerConfig,
	extra_iterations: int = 10,
	new_usage_values: Optional[Dict[ITEM_ID, Any]] = None,
) -> Dict[ITEM_ID, ItemValue]:
	"""
	Refine T/V for a specific state, using global_item_values as initialization.

	This runs a smaller number of iterations, restricted to actions that are
	feasible under the provided inventory and available recipes.
	"""
	item_values = global_item_values

	U: Dict[ITEM_ID, Dict[GAME_PHASE, float]] = {}
	T_tables: Dict[str, Dict[ITEM_ID, Dict[GAME_PHASE, float]]] = {}
	strategies: List[ValueStrategy] = []
	strategy_names = list(dict.fromkeys(config.strategies or ["max", "avg", "percentile", "custom"]))
	for s in strategy_names:
		if s == "max":
			strategies.append(MaxStrategy())
		elif s == "avg":
			strategies.append(AvgStrategy())
		elif s == "percentile":
			strategies.append(PercentileStrategy(config.percentile_target))
		elif s == "custom":
			strategies.append(CustomStrategy(config.percentile_target, config.custom_strategy_weights))
		else:
			strategies.append(MaxStrategy())
	for strat in strategies:
		T_tables[strat.name()] = {}

	for item_id, iv in item_values.items():
		U[item_id] = dict(iv.usage_value)
		if iv.transmute_values_by_strategy is not None:
			for strat in strategies:
				table = iv.transmute_values_by_strategy.get(strat.name(), None)
				if table is not None:
					T_tables[strat.name()][item_id] = dict(table)
				else:
					T_tables[strat.name()][item_id] = dict(iv.transmute_value)
		else:
			for strat in strategies:
				T_tables[strat.name()][item_id] = dict(iv.transmute_value)

	# Optionally overlay new usage values for this state.
	if new_usage_values is not None:
		for item_id, usage_entry in new_usage_values.items():
			if item_id not in U:
				continue
			
			# Parse potential tuple structure
			usage_val = None
			usage_cap = None
			if isinstance(usage_entry, tuple):
				usage_val, usage_cap = usage_entry
			elif isinstance(usage_entry, dict):
				usage_val = usage_entry
				usage_cap = item_values[item_id].usage_cap
			
			if usage_val is not None:
				iv_override = ItemValue.from_data(
					item_id=item_id,
					usage_value=dict(usage_val),
					inventory=state_inventory,
					usage_cap_single=usage_cap,
				)
				U[item_id] = dict(iv_override.usage_value)

	return _run_value_iteration_core(
		engine=engine,
		item_values=item_values,
		U=U,
		T_tables=T_tables,
		strategies=strategies,
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
