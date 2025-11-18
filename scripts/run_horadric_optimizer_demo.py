from __future__ import annotations

from math import floor

from scripts.horadric_cube.constants import (
	ENCHANTED_MINING_PICK,
	GAME_PHASE,
	GAME_PHASES,
	RECIPE_REASSEMBLE,
	STRANGE_ITEM,
	USAGE_ITEM_VALUES,
)
from scripts.horadric_cube.models import Rarity
from scripts.horadric_cube.results import HoradricEngine
from scripts.horadric_cube.optimizer import (
	OptimizerConfig,
	run_value_iteration,
	rank_items_by_transmute_gain,
	run_state_local_refinement,
	list_transmute_actions_for_state,
)


def main() -> None:
	# Build Horadric engine and default usage values.
	engine = HoradricEngine.create_horadric_engine()

	engine.item_db = engine.item_db.filter_items(
		level_min=0,
		level_max=1000,
		rarity_whitelist={Rarity.COMMON},
	)

	use_global_usage_values = True

	if use_global_usage_values:
		# Use usage values from constants as a base; items not present there
		# will default to 0.0 usage via ItemValue.from_data.
		usage_values = dict(USAGE_ITEM_VALUES)
	else:
		# Custom per-run usage values for experimentation.
		usage_values = {
			item_id: {-1: 0.0} for item_id in engine.item_db.items.keys()
		}

		# Example: seed STRANGE_ITEM with a non-zero usage baseline.
		if STRANGE_ITEM in usage_values:
			usage_values[STRANGE_ITEM][-1] = 1.0

	# Example config: restrict optimization to the earliest phase index (0)
	# and a modest number of candidate sets per recipe.
	phase: GAME_PHASE = 2

	num_iters = 60
	config = OptimizerConfig(
		recipes_included={RECIPE_REASSEMBLE},
		ingredient_rarity_whitelist={Rarity.COMMON},
		phases_included={phase},
		# Base greedy/random, with per-recipe tweaks via recipe_id keys.
		greedy_sets_per_recipe={-1: 100, RECIPE_REASSEMBLE: 0},
		random_sets_per_recipe={-1: 5000, RECIPE_REASSEMBLE: 0},

		num_iterations=num_iters,
	)

	item_values = run_value_iteration(
		engine=engine,
		usage_values=usage_values,
		config=config,
	)

	print("=== Top transmute-gain items in phase", phase, "=== ")
	for item_id, gain in rank_items_by_transmute_gain(item_values, phase, top_n=10):
		print(f"Item {item_id}: gain {gain:.3f}")

	# Simple demo state: one copy of every item
	state_inventory = {item_id: 1 for item_id in engine.item_db.items.keys()}

	# Run a small state-local refinement using the current inventory and
	# original usage values, to incorporate inventory-aware usage caps.
	state_item_values = run_state_local_refinement(
		engine=engine,
		global_item_values=item_values,
		state_inventory=state_inventory,
		state_recipes_available=None,
		config=config,
		extra_iterations=num_iters,
		new_usage_values=usage_values,
	)

	print("=== Top transmute-gain items in phase (after state refinement)", phase, "=== ")
	for item_id, gain in rank_items_by_transmute_gain(state_item_values, phase, top_n=10):
		print(f"Item {item_id}: gain {gain:.3f}")

	# List and display the best transmute actions for this state.
	actions = list_transmute_actions_for_state(
		engine=engine,
		item_values=state_item_values,
		state_inventory=state_inventory,
		state_recipes_available=None,
		phase=phase,
		config=config,
	)

	print()
	
	print("Top transmute actions for the demo state (recipe, ingredients, delta):")
	for recipe_id, ingredients, delta in actions[:10]:
		ingredient_levels = [engine.item_db.items[ingredient].required_wave_level for ingredient in ingredients]
		# avg level as computed by YouTD2 (floor)
		average_level = floor(sum(ingredient_levels) / len(ingredient_levels))
		print(f"  Recipe {recipe_id}, ingredients {list(ingredients)}, delta {delta:.3f}, average level {average_level}")

		# Per-ingredient details (ID, name, level, value in this phase).
		print("    Ingredients:")
		for ing in ingredients:
			item = engine.item_db.items.get(int(ing))
			if item is None:
				print(f"      Item {ing}, (missing in DB)")
				continue
			iv = state_item_values.get(int(ing))
			if iv is not None:
				usage_val = iv.usage_value.get(phase, 0.0)
				transmute_val = iv.transmute_value.get(phase, 0.0)
			else:
				usage_val = 0.0
				transmute_val = 0.0
			print(
				f"      Item {ing} '{item.name_english}', "
				f"level {item.required_wave_level}, "
				f"usage value {usage_val:.3f}, transmute value {transmute_val:.3f}"
			)

		# Show drop tables with probabilities and values for this action.
		recipe = engine.recipe_db.recipes[recipe_id]

		# Infer ingredient rarity from first permanent ingredient (all are common here,
		# but we keep it generic).
		ingredient_rarity = None
		for ing in ingredients:
			item = engine.item_db.items.get(int(ing))
			if item is not None and item.is_permanent:
				ingredient_rarity = item.rarity
				break
		if ingredient_rarity is None:
			# Fallback to common if no permanents are present.
			ingredient_rarity = Rarity.COMMON

		result_rarity = ingredient_rarity + recipe.rarity_change

		dist = engine.get_single_result_distribution(
			recipe_id=recipe_id,
			avg_permanent_level=average_level,
			result_rarity=result_rarity,
			explicit_ingredient_ids=ingredients,
		)

		# Sort distribution by probability and show top entries with values.
		print("    Result distribution (top 10):")
		sorted_dist = sorted(dist.items(), key=lambda x: x[1], reverse=True)
		for item_id, prob in sorted_dist[:10]:
			if item_id == 0:
				print(f"      Item 0 (sentinel), prob {prob*100:.2f}%")
				continue
			item = engine.item_db.items.get(int(item_id))
			if item is None:
				print(f"      Item {item_id}, prob {prob*100:.2f}% (missing in DB)")
				continue
			iv = state_item_values.get(int(item_id))
			if iv is not None:
				usage_val = iv.usage_value.get(phase, 0.0)
				transmute_val = iv.transmute_value.get(phase, 0.0)
			else:
				usage_val = 0.0
				transmute_val = 0.0
			print(
				f"      Item {item_id} '{item.name_english}', "
				f"level {item.required_wave_level}, "
				f"prob {prob*100:.2f}%, "
				f"usage value {usage_val:.3f}, transmute value {transmute_val:.3f}"
			)


if __name__ == "__main__":
	main()


