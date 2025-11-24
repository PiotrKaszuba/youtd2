import sys
import pytest
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

# Add parent directory to path so we can import modules
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from scripts.horadric_cube.constants import (
	ItemValue, GAME_PHASE, GAME_PHASES, ITEM_ID, GAME_PHASE_VALUE_DICT,
	FAMILY_INFO, FAMILY_RULES, FamilyRule, get_item_family_info, USAGE_ITEM_VALUES
)
from scripts.horadric_cube.optimizer import _make_value_func

# --- Fixtures ---

@pytest.fixture(autouse=True)
def clean_registry():
	"""
	Fixture to clear and restore global registries (FAMILY_RULES, USAGE_ITEM_VALUES)
	before and after each test.
	"""
	original_family_rules = FAMILY_RULES.copy()
	original_usage_values = USAGE_ITEM_VALUES.copy()
	
	FAMILY_RULES.clear()
	USAGE_ITEM_VALUES.clear()
	
	yield
	
	FAMILY_RULES.clear()
	FAMILY_RULES.update(original_family_rules)
	USAGE_ITEM_VALUES.clear()
	USAGE_ITEM_VALUES.update(original_usage_values)

@pytest.fixture
def create_item_value():
	"""
	Factory fixture to create and register ItemValue objects.
	"""
	def _factory(
		item_id: int, 
		base_val: float, 
		cap_count: Optional[int] = None, 
		cap_val: float = 0.0,
		family_info: Optional[FAMILY_INFO] = None
	) -> ItemValue:
		usage_val = {p: base_val for p in range(len(GAME_PHASES))}
		transmute_val = {p: 0.0 for p in range(len(GAME_PHASES))}
		cap = (cap_count, cap_val) if cap_count is not None else None
		
		# Register in global USAGE_ITEM_VALUES so helper functions work
		USAGE_ITEM_VALUES[item_id] = (usage_val, cap, family_info)
		
		return ItemValue(
			item_id=item_id,
			usage_value=usage_val,
			transmute_value=transmute_val,
			usage_cap=cap,
			family_info=family_info
		)
	return _factory

# --- Tests ---

def test_basic_cap_logic(create_item_value):
	"""Test standard usage cap logic without families or consumption."""
	# Item 1: Val 10.0, Cap 2, Overflow 1.0
	iv = create_item_value(1, 10.0, 2, 1.0)
	item_values = {1: iv}
	phase = 0
	
	# Case 1: No inventory -> Full Value
	vf_none = _make_value_func(item_values, phase, state_inventory={})
	assert vf_none(1) == 10.0

	# Case 2: Inventory below cap (1 < 2) -> Full Value
	vf_under = _make_value_func(item_values, phase, state_inventory={1: 1})
	assert vf_under(1) == 10.0

	# Case 3: Inventory at cap (2 >= 2) -> Overflow Value
	vf_at_cap = _make_value_func(item_values, phase, state_inventory={1: 2})
	assert vf_at_cap(1) == 1.0

@pytest.mark.parametrize("initial_count, consume_count, expected_value", [
	(2, 0, 1.0),   # Have 2 (Cap 2). Next item is overflow.
	(2, 1, 10.0),  # Have 2. Consume 1. Effective 1. Value of removed item is Full.
	(3, 1, 1.0),   # Have 3. Consume 1. Effective 2. Still at cap. Value of removed item is Low.
	(3, 2, 10.0),  # Have 3. Consume 2. Effective 1. Value of 2nd removed item is Full.
])
def test_consume_logic(create_item_value, initial_count, consume_count, expected_value):
	"""Test that 'consume_count' correctly reduces effective inventory for valuation."""
	iv = create_item_value(1, 10.0, 2, 1.0)
	item_values = {1: iv}
	phase = 0
	
	vf = _make_value_func(item_values, phase, state_inventory={1: initial_count})
	assert vf(1, consume_count=consume_count) == expected_value

def test_family_shadowing_basic(create_item_value):
	"""Test that higher tier item counts towards lower tier cap."""
	FAMILY_RULES[100] = FamilyRule(downward_impacts={1: {-1: 1.0}})
	
	# Low Tier (T1)
	iv1 = create_item_value(1, 10.0, 2, 1.0, family_info=(100, 1, {}))
	# High Tier (T2)
	iv2 = create_item_value(2, 50.0, None, 0.0, family_info=(100, 2, {}))
	
	item_values = {1: iv1, 2: iv2}
	phase = 0
	
	# Have 1x T1 + 1x T2 -> Effective T1 = 2 (Cap).
	inventory = {1: 1, 2: 1}
	vf = _make_value_func(item_values, phase, state_inventory=inventory)
	
	assert vf(1) == 1.0
	
	# Control: Without High Tier -> Effective T1 = 1 (< Cap).
	inventory_solo = {1: 1}
	vf_solo = _make_value_func(item_values, phase, state_inventory=inventory_solo)
	assert vf_solo(1) == 10.0

def test_family_shadowing_fractional(create_item_value):
	"""Test fractional shadowing logic."""
	# +1 Tier -> 0.5
	FAMILY_RULES[100] = FamilyRule(downward_impacts={1: {-1: 0.5}})
	
	iv1 = create_item_value(1, 10.0, 2, 1.0, family_info=(100, 1, {}))
	iv2 = create_item_value(2, 50.0, None, 0.0, family_info=(100, 2, {}))
	
	item_values = {1: iv1, 2: iv2}
	phase = 0
	
	# 1x T1 + 1x T2 -> Effective = 1.5 < 2. Full Value.
	inventory = {1: 1, 2: 1}
	vf = _make_value_func(item_values, phase, state_inventory=inventory)
	assert vf(1) == 10.0
	
	# 1x T1 + 2x T2 -> Effective = 2.0 >= 2. Overflow Value.
	inventory_full = {1: 1, 2: 2}
	vf_full = _make_value_func(item_values, phase, state_inventory=inventory_full)
	assert vf_full(1) == 1.0

def test_family_shadowing_multi_tier(create_item_value):
	"""Test interactions across multiple tier gaps."""
	FAMILY_RULES[100] = FamilyRule(downward_impacts={
		1: {-1: 1.0}, 
		2: {-1: 0.5}
	})
	
	iv1 = create_item_value(1, 10.0, 3, 1.0, family_info=(100, 1, {}))
	iv2 = create_item_value(2, 20.0, None, 0.0, family_info=(100, 2, {}))
	iv3 = create_item_value(3, 30.0, None, 0.0, family_info=(100, 3, {}))
	
	item_values = {1: iv1, 2: iv2, 3: iv3}
	phase = 0
	
	# 1x T1 + 1x T2 + 1x T3 -> Eff = 1 + 1.0 + 0.5 = 2.5 < 3.
	inventory = {1: 1, 2: 1, 3: 1}
	vf = _make_value_func(item_values, phase, state_inventory=inventory)
	assert vf(1) == 10.0
	
	# Add another T3 -> Eff = 1 + 1.0 + 1.0 = 3.0 >= 3.
	inventory[3] = 2
	vf_full = _make_value_func(item_values, phase, state_inventory=inventory)
	assert vf_full(1) == 1.0

def test_phase_specific_impacts(create_item_value):
	"""Test that shadowing impact varies by phase."""
	FAMILY_RULES[100] = FamilyRule(downward_impacts={
		1: {0: 1.0, 1: 0.0}
	})
	
	iv1 = create_item_value(1, 10.0, 2, 1.0, family_info=(100, 1, {}))
	iv2 = create_item_value(2, 50.0, None, 0.0, family_info=(100, 2, {}))
	item_values = {1: iv1, 2: iv2}
	inventory = {1: 1, 2: 1}
	
	# Phase 0: Eff = 2 (Cap). Overflow.
	vf0 = _make_value_func(item_values, 0, state_inventory=inventory)
	assert vf0(1) == 1.0
	
	# Phase 1: Eff = 1 (< Cap). Full Value.
	vf1 = _make_value_func(item_values, 1, state_inventory=inventory)
	assert vf1(1) == 10.0

def test_complex_consumption_and_shadowing(create_item_value):
	"""
	Test that consumption reduces item count but shadowing maintains cap status.
	"""
	FAMILY_RULES[100] = FamilyRule(downward_impacts={1: {-1: 1.0}})
	
	iv1 = create_item_value(1, 10.0, 1, 1.0, family_info=(100, 1, {})) # Cap 1
	iv2 = create_item_value(2, 50.0, None, 0.0, family_info=(100, 2, {}))
	
	item_values = {1: iv1, 2: iv2}
	phase = 0
	
	# 1x T1, 1x T2. Eff T1 = 2.
	inventory = {1: 1, 2: 1}
	vf = _make_value_func(item_values, phase, state_inventory=inventory)
	
	# Consume 1x T1. Eff = (1-1) + 1 = 1.
	# 1 >= Cap(1). Value should still be Overflow (1.0).
	# Meaning: Losing the T1 is cheap because T2 covers the utility.
	assert vf(1, consume_count=1) == 1.0
	
	# Without T2: Eff = 0. Value = Full.
	inventory_solo = {1: 1}
	vf_solo = _make_value_func(item_values, phase, state_inventory=inventory_solo)
	assert vf_solo(1, consume_count=1) == 10.0

def test_missing_family_rule_graceful_fail(create_item_value):
	"""Item has family info but no global rule."""
	iv = create_item_value(1, 10.0, 2, 1.0, family_info=(999, 1, {}))
	item_values = {1: iv}
	inventory = {1: 1}
	
	vf = _make_value_func(item_values, 0, state_inventory=inventory)
	assert vf(1) == 10.0

def test_circular_or_same_tier_shadowing(create_item_value):
	"""Same-tier items can share caps when rule defines tier_diff=0."""
	FAMILY_RULES[100] = FamilyRule(downward_impacts={0: {-1: 1.0}})
	
	iv1 = create_item_value(1, 10.0, 2, 1.0, family_info=(100, 1, {}))
	iv2 = create_item_value(2, 10.0, 2, 1.0, family_info=(100, 1, {})) # Same tier
	
	item_values = {1: iv1, 2: iv2}
	# 1x T1, 5x T1(Peer). Eff T1 should be 1.
	inventory = {1: 1, 2: 5}
	
	vf = _make_value_func(item_values, 0, state_inventory=inventory)
	assert vf(1) == 1.0


def test_multi_family_membership(create_item_value):
	"""Items belonging to multiple families accumulate all applicable shadows."""
	FAMILY_RULES[100] = FamilyRule(downward_impacts={1: {-1: 1.0}})
	FAMILY_RULES[200] = FamilyRule(downward_impacts={1: {-1: 1.0}})
	
	iv_base = create_item_value(
		1,
		10.0,
		2,
		1.0,
		family_info=[(100, 1, {}), (200, 1, {})],
	)
	iv_a = create_item_value(2, 50.0, None, 0.0, family_info=(100, 2, {}))
	iv_b = create_item_value(3, 60.0, None, 0.0, family_info=(200, 2, {}))
	item_values = {1: iv_base, 2: iv_a, 3: iv_b}
	inventory = {1: 1, 2: 1, 3: 1}
	vf = _make_value_func(item_values, 0, state_inventory=inventory)
	# Each family contributes 1 shadow count -> effective = 1 (self) + 1 + 1 = 3 >= cap.
	assert vf(1) == 1.0