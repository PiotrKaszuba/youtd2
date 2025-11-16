# Horadric Cube Sim Analysis

## Bugs (Critical / Resolved)

### 1. Fallback mechanism for empty pools (resolved)
**Severity:** MEDIUM  
**Location:** `get_permanent_item_pool_bounded`, `build_single_result_decision_tree`  
**Issue:** Godot's HoradricCube logic lowers `lvl_min` by 10 repeatedly (up to 10 times) when the permanent-item pool is empty. The Python version now mirrors this behavior via the `with_fallback=True` option used by the HoradricCube-style result generation.\
**Status:** Implemented – the default mode has no fallback (matching `ItemDropCalc.get_item_list_bounded`), while HoradricCube usage opts into fallback explicitly.

### 2. Result rarity handling
**Severity:** LOW  
**Location:** `compute_result_rarity`, `find_best_avg_level_for_item`  
**Issue:** Result rarity can theoretically go out of bounds if misconfigured data is used. In practice, CSV data keeps rarity within range. The Python code now mirrors Godot (no clamping) and adds an optional ingredient-rarity inference path based on the target item's rarity and the recipe's `rarity_change`.\
**Status:** Behavior matches Godot; inference raises a clear `ValueError` if it would go out of bounds.

### 3. Sentinel item ID 0
**Severity:** LOW  
**Location:** `build_single_result_decision_tree`, `get_single_result_distribution`  
**Issue:** Returns item ID `0` when pools are empty. In this project, item IDs start at 1 and Godot already uses `0` as a sentinel “no item” value in `ItemDropCalc` and HoradricCube.\
**Status:** Confirmed intentional – comments now document 0 as the sentinel “no item” ID, and distributions may include `0` to represent failure / empty-pool cases.

## Performance Issues

### 1. Repeated pool building
**Severity:** MEDIUM  
**Location:** `build_single_result_decision_tree`  
**Issue:** Pools are rebuilt for each luck value, but many luck values may have overlapping level ranges.  
**Impact:** O(n * 4) pool builds where n is number of items, could be optimized.  
**Fix:** Cache pools by (rarity, lvl_min, lvl_max) or pre-compute all pools.

### 2. Linear item iteration in pool functions
**Severity:** LOW  
**Location:** `get_permanent_item_pool_bounded`, `get_oil_and_consumable_pool`  
**Issue:** Iterates through all items each time.  
**Impact:** O(n) per call, but n is likely small (< 1000 items).  
**Fix:** Pre-index items by rarity/type if profiling shows bottleneck.

## Maintainability Issues

### 1. Hard-coded recipe ID in main()
**Severity:** LOW (FIXED)  
**Location:** `main()` function  
**Issue:** Used hard-coded `3` instead of constant.  
**Status:** Fixed by adding `RECIPE_REASSEMBLE` constant.

### 2. Incomplete type hints
**Severity:** LOW  
**Location:** Various functions  
**Issue:** Some return types could be more specific (e.g., `Dict[int, float]` vs `Dict`).  
**Impact:** Reduced IDE support and type checking.

### 3. Magic numbers
**Severity:** LOW  
**Location:** `compute_level_bounds_for_recipe` (line 314: `100000`)  
**Issue:** Large magic number for PRECIPITATE level bound.  
**Fix:** Extract to constant `MAX_LEVEL_BOUND = 100000`.

## Proposed Improvements

### 1. Add validation helpers
- `validate_result_rarity(rarity: int) -> int` - clamps to [0, 3]
- `validate_recipe_ingredients()` - checks counts match recipe requirements

### 4. Better error handling
- Raise `ValueError` with clear messages instead of returning 0 for empty pools
- Add `EmptyPoolError` exception class

### 5. Recursive roll function
Replace manual double-roll in `roll_single_result` with recursive helper:
```python
def _roll_recursive(node: DecisionNode, rng: np.random.Generator) -> int:
    outcome = node.roll(rng)
    if isinstance(outcome, DecisionNode):
        return _roll_recursive(outcome, rng)
    return int(outcome)
```

## Proposed Analytics

### 1. Multi-item result distributions
- Joint probability distributions for recipes with `result_count > 1`
- Expected number of target items in multi-result recipes
- Probability of getting at least N copies of target item

### 2. Expected value calculations
- Expected item level of results
- Expected rarity distribution
- Expected value of result items (if cost/rarity values available)

### 3. Level range optimization
- Find optimal level range (not just single level) for target item
- Sensitivity analysis: how probability changes with ±1 level
- Level ranges that guarantee non-zero probability

### 4. Ingredient composition analysis
- Best ingredient combinations for target item
- Trade-offs between explicit items vs aggregate levels
- Rarity optimization (which ingredient rarity maximizes target probability)

### 5. Recipe comparison
- Compare recipes for obtaining same target item
- Efficiency metrics (ingredients per target item probability)
- Resource cost analysis

### 6. Monte Carlo simulation
- Simulate N recipe uses and track outcomes
- Confidence intervals for target item probability
- Convergence analysis

