<!-- 4aadcad4-a248-47c1-8bba-c0831b963670 cc1a8cdc-f72c-4e6e-9694-964de5071889 -->
# Horadric Value Optimization Engine – Updated Plan

### Summary of key design decisions

- **Value semantics**
  - `U[i, phase]` = fixed usage value (from design or data).
  - `T[i, phase]` = **absolute transmute value**: expected value of the *best* recipe chain starting from item `i` in that phase (not a delta).
  - `V[i, phase] = max(U[i, phase], T[i, phase])` = current best value for item `i`.
- **Global vs state-local**
  - First compute a **global value function** `T_global` assuming a configurable universe of recipes / ingredient constraints (inventory-agnostic, but steerable).
  - For a concrete game state (inventory, phase, unlocked recipes), use `T_global` / `V_global` to:
    - Score all **feasible** transmute actions (recipe + ingredient set) and pick the best one.
  - Optional **state-local refinement**: when needed, initialize `T_state` from `T_global` and run a few local iterations using the *actual state* (inventory and recipe availability) as constraints.
- **Action semantics**
  - Each transmute action `(recipe, ingredient-set S, phase)` has a net value:

\[

\Delta = \underbrace{\mathbb{E}[\text{value(results)}]}_{\sum_j P_r(j|S,p) V[j,p]} \;-\; \underbrace{\text{ingredient\_cost}}_{\sum_{i \in S} V[i,p]}

\]

  - `T[i,p]` should approximate the **max over actions** using `i` as ingredient, not a sum; multiple recipes are mutually exclusive uses of the same item.

- **Steerability / constraints**
  - The optimizer is driven by a config object that can:
    - Include/exclude specific recipes.
    - Exclude specific items as ingredients (but still allow them as results).
    - Restrict ingredient rarity (e.g. only common ingredients) while still allowing upgraded results.
    - Restrict ingredient levels (min/max `required_wave_level`).
  - All these constraints apply to **ingredient-set generation**; result distributions always reflect the full Horadric logic given those ingredients.

---

### 1. Use existing Horadric modules and clarify interfaces

- Continue to use the existing modules as the foundation:
  - `db.py` – load `ItemDatabase`, `RecipeDatabase` from CSVs.
  - `models.py` – `Item`, `Recipe`, `Rarity`, `ResultItemType`.
  - `levels_and_pools.py` – average-level logic, level bounds, rarity inference, and item/oil pools.
  - `decision_tree.py` – `DecisionNode`, luck-node and item-choice builders, distribution flattening.
  - `results.py` – single-result decision trees, distributions, `HoradricEngine` wrapper.
  - `feasibility.py` (+ `k_sum_with_reuse.py`) – structural feasibility and inventory-aware level feasibility.
  - `constants.py` – `GAME_PHASE`, `GAME_PHASES`, `ItemValue`, `USAGE_ITEM_VALUES`, recipe / item constants.
- Treat `HoradricEngine` as the primary interface for the optimizer:
  - Access `engine.item_db`, `engine.recipe_db`.
  - Use `engine.get_single_result_distribution(...)` for single-slot result probabilities.
  - Optionally use `engine.find_best_avg_level_for_item_with_inventory` to focus on good average levels in state-local refinement.

### 2. Optimizer configuration and API

- Introduce an `OptimizerConfig` dataclass in `scripts/horadric_cube/optimizer.py` to make the engine steerable:
  ```python
  @dataclass
  class OptimizerConfig:
  	recipes_included: Optional[Set[int]] = None
  	ingredient_items_excluded: Set[int] = field(default_factory=set)
  	ingredient_rarity_whitelist: Optional[Set[int]] = None
  	ingredient_level_min: Optional[int] = None
  	ingredient_level_max: Optional[int] = None
  	max_sets_per_recipe: int = 100
  	num_iterations: int = 50
  	learning_rate: float = 0.1
  ```

- Define the main optimizer entry points in `optimizer.py`:
  ```python
  def run_value_iteration(
  	engine: HoradricEngine,
  	usage_values: Dict[ITEM_ID, GAME_PHASE_VALUE_DICT],
  	config: OptimizerConfig,
  ) -> Dict[ITEM_ID, ItemValue]:
  	...
  
  def run_state_local_refinement(
  	engine: HoradricEngine,
  	usage_values: Dict[ITEM_ID, GAME_PHASE_VALUE_DICT],
  	global_item_values: Dict[ITEM_ID, ItemValue],
  	state_inventory: Dict[ITEM_ID, int],
  	state_recipes_available: Optional[Set[int]],
  	config: OptimizerConfig,
  	extra_iterations: int = 10,
  ) -> Dict[ITEM_ID, ItemValue]:
  	"""
  	Refine T/V for a specific state, using global_item_values as initialization.
  	"""
  	...
  ```

- Add ranking helpers:
  ```python
  def rank_items_by_transmute_gain(
  	item_values: Dict[ITEM_ID, ItemValue],
  	phase: GAME_PHASE,
  	top_n: int = 20,
  ) -> List[Tuple[ITEM_ID, float]]:  # item_id, gain
  	...
  
  def rank_recipes_by_net_gain(
  	engine: HoradricEngine,
  	item_values: Dict[ITEM_ID, ItemValue],
  	phase: GAME_PHASE,
  	config: OptimizerConfig,
  ) -> List[Tuple[int, Sequence[ITEM_ID], float]]:  # recipe_id, ingredient_ids, delta
  	...
  ```


### 3. Candidate ingredient-set generation with constraints

- Implement helper(s) in `optimizer.py` to generate candidate ingredient sets `S` for each recipe and phase:
  ```python
  def generate_candidate_sets_for_recipe(
  	engine: HoradricEngine,
  	recipe_id: int,
  	phase: GAME_PHASE,
  	config: OptimizerConfig,
  	item_values: Dict[ITEM_ID, ItemValue],
  ) -> List[Sequence[ITEM_ID]]:
  	...
  ```

- Inside this helper:
  - Apply **recipe filter**: skip recipes not in `config.recipes_included` (if set).
  - Build ingredient pools via `get_permanent_item_pool_bounded` / `get_oil_and_consumable_pool`, then filter:
    - Exclude items in `ingredient_items_excluded`.
    - Only keep items whose rarity is in `ingredient_rarity_whitelist` (if provided).
    - Only keep items with `ingredient_level_min <= required_wave_level <= ingredient_level_max` (if provided).
  - Generate candidate sets matching `permanent_count` / `usable_count`:
    - Start with simple strategies (e.g. random sampling + “k lowest V[i,phase] items”), bounded by `max_sets_per_recipe` for each recipe.

- For **global optimization**, ignore inventory; for **state-local refinement**, additionally filter candidates by availability in `state_inventory` and, if desired, call `is_avg_level_feasible` / `get_feasible_avg_levels_for_recipe` to ensure structural feasibility.

### 4. Global value iteration using T as absolute value

- In `run_value_iteration`:
  - Initialize `ItemValue` for each item from `usage_values` via `ItemValue.from_data`, with `transmute_value` initially 0.
  - For each phase `p` and iteration:

    1. Compute `V[i,p] = max(U[i,p], T[i,p])` for all items.
    2. For each recipe `r` allowed by `config` and each candidate set `S` from `generate_candidate_sets_for_recipe`:

       - Select an average permanent level appropriate for phase `p` (e.g. midpoint of phase’s level range, or a small set of levels evaluated via `find_best_avg_level_for_item`).
       - Determine `result_rarity` for this recipe and ingredients (e.g. via existing rarity-change logic).
       - Use `engine.get_single_result_distribution(...)` to obtain `P_r(j | S, p)`.
       - Compute:
         ```python
         ingredient_cost = sum(V[i,p] for i in S)
         expected_result_value = sum(P[j] * V[j,p] for j in dist.keys())
         delta = expected_result_value - ingredient_cost
         ```

       - If `delta <= 0`, skip (this action doesn’t improve things under current V).
       - Otherwise, update a temporary `best_candidate_value[i,p]` for each `i in S`:
         ```python
         candidate_value = expected_result_value  # or ingredient_cost + delta
         best_candidate_value[i,p] = max(best_candidate_value[i,p], candidate_value)
         ```


    1. After processing all recipes/sets for this phase & iteration, update `T[i,p]` via a **soft max** toward the best candidate value:
       ```python
       T[i,p] = (1 - alpha) * T[i,p] + alpha * best_candidate_value[i,p]
       ```

    1. Recompute `V[i,p] = max(U[i,p], T[i,p])`.

- Return a `Dict[ITEM_ID, ItemValue]` with `usage_value` fixed and `transmute_value` filled from learned `T`.

### 5. State-local refinement option

- `run_state_local_refinement` should:
  - Take `global_item_values` as input and copy them into a **state-local** structure (e.g. `T_state[i,p] = global T[i,p]`).
  - Restrict actions by:
    - Available recipes `state_recipes_available` (intersection with `config.recipes_included`).
    - Actual `state_inventory` via:
      - Filtering candidate sets to respect counts.
      - Optional feasibility checks via `is_avg_level_feasible` / `get_feasible_avg_levels_for_recipe`.
  - Run a small number (`extra_iterations`) of iterations of the same update logic **only over feasible actions** in this state.
  - Produce `ItemValue` objects reflecting `T_state`, which can be used to:
    - Score current actions more accurately.
    - Inspect how the local constraints change item priorities.

### 6. Best-transmute decision in a given state

- Provide a helper in `optimizer.py` to recommend the best transmute action for a specific state:
  ```python
  def choose_best_transmute_action(
  	engine: HoradricEngine,
  	item_values: Dict[ITEM_ID, ItemValue],  # global or state-local
  	state_inventory: Dict[ITEM_ID, int],
  	state_recipes_available: Optional[Set[int]],
  	phase: GAME_PHASE,
  	config: OptimizerConfig,
  ) -> Optional[Tuple[int, Sequence[ITEM_ID], float]]:
  	"""Return (recipe_id, ingredient_ids, action_value) or None if no profitable action exists."""
  	...
  ```

- Inside:
  - Generate feasible `(recipe, S)` pairs under inventory and config constraints.
  - For each, compute `action_value = expected_result_value - ingredient_cost` using current `V[i,p]`.
  - Return the argmax with `action_value > 0`; if none, return `None` (keep items).

### 7. Ranking helpers

- `rank_items_by_transmute_gain`:
  - For each item `i` in phase `p`, compute `gain_i = T[i,p] - U[i,p]`.
  - Sort items by `gain_i` descending; items with large positive gain are good fodder (better to transmute than to use directly).
- `rank_recipes_by_net_gain`:
  - Reuse the same candidate `(recipe, S)` enumeration and delta computation as in the optimizer.
  - Collect `(recipe_id, S, delta)` triples with `delta > 0` and sort descending by `delta`.

### 8. Testing and CLI integration

- Keep existing tests untouched and passing.
- Add tests for `optimizer.py`:
  - Tiny synthetic Horadric setup where one recipe clearly upgrades an item’s value; assert that `T` converges near the upgraded value and `gain > 0`.
  - A synthetic “loss recipe” to assert that it doesn’t increase `T` and is not chosen by `choose_best_transmute_action`.
  - Tests for respecting constraints from `OptimizerConfig`.
- Extend or complement `run_horadric_cube_sim.py`:
  - Add a mode that runs `run_value_iteration` on the real data with a simple config.
  - Print top-N fodder items and top-N profitable recipes for a chosen phase.
  - Optionally add a mode that, given a sample inventory, calls `choose_best_transmute_action` and prints the recommended transmute.

### 9. Style and project preferences

- Follow [TAB_INDENTATION] (tabs only for indentation).
- Keep new code localized to `scripts/horadric_cube/optimizer.py` + minimal additions to CLI (`run_horadric_cube_sim.py`) per [MINIMAL_TOUCH].
- Use type hints and existing aliases (`ITEM_ID`, `GAME_PHASE`, etc.) in new functions per [PREFER_TYPE_HINTS].
- Favor small, composable helpers ([CODE_IS_LIABILITY], [DEDUPLICATE]) and avoid prematurely introducing complex symbolic “pluggable equations” – we rely instead on the iterative max-based value iteration and optional state-local refinement.

### To-dos

- [ ] Define the public API and data flow for the value optimizer (run_value_iteration, state-local refinement, ranking helpers) in a new optimizer module that uses HoradricEngine and ItemValue.
- [ ] Implement per-phase value iteration in optimizer.py using U/T/V semantics, HoradricEngine for distributions, opportunity-cost-based delta, and a max-based update for T as absolute values.
- [ ] Implement utilities to rank items by transmute gain and recipes by net gain per phase, using learned ItemValue data and OptimizerConfig constraints.
- [ ] Create synthetic tests validating that T converges to correct values, profitable recipes/ingredients are ranked appropriately, and constraints are respected, while keeping existing tests passing.
- [ ] Extend or complement run_horadric_cube_sim.py to run the optimizer on real data, print top fodder items and profitable recipes, and optionally recommend best transmute action for a sample inventory.