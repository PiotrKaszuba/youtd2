import sys
import pytest
import pickle
from pathlib import Path
from typing import Dict, Any, List, Set

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from scripts.horadric_cube.results import HoradricEngine
from scripts.horadric_cube.optimizer import (
	OptimizerConfig,
	_make_value_func,
	generate_candidate_sets_for_recipe,
	_compute_action_value,
)
from scripts.horadric_cube.models import Rarity
from scripts.horadric_cube.constants import (
	USAGE_ITEM_VALUES,
	GAME_PHASES,
	ItemValue,
	FAMILY_RULES,
	FamilyRule,
	get_game_phase_index,
	Inventory,
	RECIPE_PERFECT,
	RECIPE_REASSEMBLE,
	# Import specific items for scenario construction
	RUSTY_MINING_PICK, VOID_VIAL, ASSASINATION_ARROW, TRAINING_MANUAL,
	YOUNG_THIEF_CLOAK, SKULL_TROPHY, RING_OF_LUCK, SCARAB_AMULET,
	MAGIC_GLOVES, SPIDER_SILK, ORC_WAR_SPEAR, MAGICAL_ESSENCE
)

@pytest.fixture(scope="session")
def engine():
	"""Load the real game engine with real items/recipes."""
	eng = HoradricEngine.create_horadric_engine()
	eng.item_db = eng.item_db.filter_items(
		level_min=0,
		level_max=1000,
		rarity_whitelist={Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE, Rarity.UNIQUE},
	)
	return eng

@pytest.fixture(scope="session")
def real_item_values(engine):
	"""Load optimized item values from the pickle file (if exists) or run quick iteration."""
	pkl_path = Path("item_values.pkl")
	if pkl_path.exists():
		with open(pkl_path, "rb") as f:
			return pickle.load(f)
	else:
		pytest.skip("item_values.pkl not found - run server or optimizer first to generate values.")

@pytest.fixture
def clean_state():
	"""Clear/restore global constants for test isolation."""
	orig_family_rules = FAMILY_RULES.copy()
	orig_usage = USAGE_ITEM_VALUES.copy()
	yield
	FAMILY_RULES.clear()
	FAMILY_RULES.update(orig_family_rules)
	USAGE_ITEM_VALUES.clear()
	USAGE_ITEM_VALUES.update(orig_usage)

def _update_item_caps(item_id: int, cap_tuple: tuple):
	"""Helper to patch usage caps for a specific test."""
	val = USAGE_ITEM_VALUES.get(item_id)
	if val:
		# Handle both 2-tuple and 3-tuple formats
		if len(val) == 2:
			usage, _ = val
			USAGE_ITEM_VALUES[item_id] = (usage, cap_tuple)
		else:
			usage, _, fam = val
			USAGE_ITEM_VALUES[item_id] = (usage, cap_tuple, fam)

def _update_item_family(item_id: int, family_info: tuple):
	"""Helper to patch family info."""
	val = USAGE_ITEM_VALUES.get(item_id)
	if val:
		if len(val) == 2:
			usage, cap = val
			USAGE_ITEM_VALUES[item_id] = (usage, cap, family_info)
		else:
			usage, cap, _ = val
			USAGE_ITEM_VALUES[item_id] = (usage, cap, family_info)

def test_delta_calculation_with_caps(engine, real_item_values, clean_state):
	"""
	Integration test: Calculate delta for a recipe where ingredients are at cap.
	"""
	# Scenario:
	# Use RUSTY_MINING_PICK (Common) as ingredient.
	# Recipe: Reassemble (3 -> 1 same rarity) or Perfect (3 -> 1 higher rarity).
	# Let's assume we check Perfect recipe for simplicity of value gain logic.
	
	recipe_id = RECIPE_PERFECT # 3 Common -> 1 Uncommon
	phase = 0 # Early game
	
	# 1. Set up item values/caps
	# Pick 1: Cap 2. Value High (10.0). Overflow Low (1.0).
	# We want to simulate having 3 Picks.
	# Ingredient cost for using 1 Pick should be Low (1.0) because remaining 2 are enough for cap.
	
	# Mock the usage values in the loaded `real_item_values` dict effectively
	# Note: `real_item_values` is a dict of ItemValue objects. We need to patch it or `USAGE_ITEM_VALUES`?
	# The optimizer functions use `item_values` passed to them.
	
	# Create a modified ItemValue for the test
	base_iv = real_item_values[RUSTY_MINING_PICK]
	
	# Force specific values for predictability
	usage_val = {p: 10.0 for p in range(len(GAME_PHASES))}
	transmute_val = {p: 0.0 for p in range(len(GAME_PHASES))}
	# Cap at 2, Overflow at 1.0
	test_iv = ItemValue(
		item_id=RUSTY_MINING_PICK,
		usage_value=usage_val,
		transmute_value=transmute_val,
		usage_cap=(2, 1.0),
		family_info=None
	)
	
	test_item_values = real_item_values.copy()
	test_item_values[RUSTY_MINING_PICK] = test_iv
	
	# Inventory: 3 Picks (Above Cap)
	inventory = {RUSTY_MINING_PICK: 3}
	
	# Value function
	value_func = _make_value_func(test_item_values, phase, state_inventory=inventory)
	
	# Compute Action
	S = [RUSTY_MINING_PICK, RUSTY_MINING_PICK, RUSTY_MINING_PICK]
	recipe = engine.recipe_db.recipes[recipe_id]
	
	result_val, delta = _compute_action_value(
		engine=engine,
		recipe=recipe,
		S=S,
		phase=phase,
		value_func=value_func
	)
	
	# Analysis of Expected Cost:
	# Item 1: Consumed from count 3 -> 2. Effective = 2 (At Cap). Value lost = Overflow (1.0).
	# Item 2: Consumed from count 2 -> 1. Effective = 1 (< Cap). Value lost = Full (10.0).
	# Item 3: Consumed from count 1 -> 0. Effective = 0 (< Cap). Value lost = Full (10.0).
	# Total Ingredient Cost = 1.0 + 10.0 + 10.0 = 21.0
	
	# Verify cost manually by summing individual calls
	cost_1 = value_func(RUSTY_MINING_PICK, consume_count=1) # 1.0
	cost_2 = value_func(RUSTY_MINING_PICK, consume_count=2) # 10.0
	cost_3 = value_func(RUSTY_MINING_PICK, consume_count=3) # 10.0
	
	assert cost_1 == 1.0
	assert cost_2 == 10.0
	assert cost_3 == 10.0
	
	expected_cost = 21.0
	calculated_cost = result_val - delta
	
	assert abs(calculated_cost - expected_cost) < 0.001

def test_family_shadowing_integration(engine, real_item_values, clean_state):
	"""
	Integration test: High tier item shadowing low tier item in cost calculation.
	"""
	# Setup: Family 999.
	# T1 Item: VOID_VIAL. Cap 1. Value 100. Overflow 5.
	# T2 Item: SCARAB_AMULET. Shadows T1 by 1.0.
	
	fam_id = 999
	FAMILY_RULES[fam_id] = FamilyRule(downward_impacts={1: {-1: 1.0}}) # +1 tier -> 1.0 shadow
	
	phase = 0
	
	# Modify ItemValues
	t1_id = VOID_VIAL
	t2_id = SCARAB_AMULET
	
	t1_iv = ItemValue(
		item_id=t1_id,
		usage_value={p: 100.0 for p in range(len(GAME_PHASES))},
		transmute_value={p: 0.0 for p in range(len(GAME_PHASES))},
		usage_cap=(1, 5.0),
		family_info=(fam_id, 1, {})
	)
	
	t2_iv = ItemValue(
		item_id=t2_id,
		usage_value={p: 50.0 for p in range(len(GAME_PHASES))}, # Doesn't matter for T1 cost
		transmute_value={p: 0.0 for p in range(len(GAME_PHASES))},
		usage_cap=None,
		family_info=(fam_id, 2, {})
	)
	
	test_item_values = real_item_values.copy()
	test_item_values[t1_id] = t1_iv
	test_item_values[t2_id] = t2_iv
	
	# Update global registry so helper `get_item_family_info` works inside `_make_value_func`
	USAGE_ITEM_VALUES[t1_id] = (t1_iv.usage_value, t1_iv.usage_cap, t1_iv.family_info)
	USAGE_ITEM_VALUES[t2_id] = (t2_iv.usage_value, t2_iv.usage_cap, t2_iv.family_info)
	
	# Inventory: 1x T1, 1x T2.
	# Effective T1 count = 1 (self) + 1 (shadow) = 2. (Above Cap 1).
	inventory = {t1_id: 1, t2_id: 1}
	
	vf = _make_value_func(test_item_values, phase, state_inventory=inventory)
	
	# Calculate cost of using the T1 item
	# consume_count = 1.
	# effective = (1 - 1) + 1 (shadow) = 1.
	# 1 >= Cap 1. Value should be Overflow (5.0).
	cost = vf(t1_id, consume_count=1)
	
	assert cost == 5.0
	
	# Contrast: Remove T2 from inventory
	inventory_solo = {t1_id: 1}
	vf_solo = _make_value_func(test_item_values, phase, state_inventory=inventory_solo)
	# effective = 0. < Cap. Value = Full (100.0)
	cost_solo = vf_solo(t1_id, consume_count=1)
	
	assert cost_solo == 100.0

def test_recipe_generation_and_valuation(engine, real_item_values, clean_state):
	"""
	End-to-end flow: Generate candidates for a real inventory and verify they include expected items.
	"""
	# Inventory from server.py example
	transmute_items = [
		{"id": RUSTY_MINING_PICK, "uid": 2}, # Common
		{"id": VOID_VIAL, "uid": 3}, # Common
		{"id": ASSASINATION_ARROW, "uid": 4}, # Common
		{"id": TRAINING_MANUAL, "uid": 5}, # Common
		{"id": YOUNG_THIEF_CLOAK, "uid": 6}, # Common
		{"id": SKULL_TROPHY, "uid": 7}, # Common
		{"id": RING_OF_LUCK, "uid": 8}, # Common
		{"id": SCARAB_AMULET, "uid": 9}, # Common
	]
	
	# Helper to convert to inventory dict
	inv = {}
	for item in transmute_items:
		tid = item['id']
		inv[tid] = inv.get(tid, 0) + 1
		
	phase = 0
	recipe_id = RECIPE_REASSEMBLE # 3 -> 1 same rarity
	
	config = OptimizerConfig(
		recipes_included={recipe_id},
		phases_included={phase},
		ingredient_rarity_whitelist={Rarity.COMMON},
		greedy_sets_per_recipe={-1: 50},
		random_sets_per_recipe={-1: 50}
	)
	
	# Generate candidates
	candidates = generate_candidate_sets_for_recipe(
		engine=engine,
		recipe_id=recipe_id,
		phase=phase,
		config=config,
		item_values=real_item_values,
		state_inventory=inv
	)
	
	# Should find at least some candidates given we have 8 commons
	assert len(candidates) > 0
	
	# Check that we can compute values for them
	vf = _make_value_func(real_item_values, phase, state_inventory=inv)
	recipe = engine.recipe_db.recipes[recipe_id]
	
	for S in candidates:
		# S is list of item IDs
		assert len(S) == 3 # Reassemble takes 3
		
		# Check valuation
		res_val, delta = _compute_action_value(
			engine=engine,
			recipe=recipe,
			S=S,
			phase=phase,
			value_func=vf
		)
		
		# Verify delta logic: Delta = Result - Cost
		cost = 0.0
		item_counts = {}
		for i in S:
			item_counts[i] = item_counts.get(i, 0) + 1
			cost += vf(i, consume_count=item_counts[i])
			
		assert abs((res_val - cost) - delta) < 0.001

if __name__ == "__main__":
	# Allow running directly
	pytest.main([__file__])

