from __future__ import annotations

from pathlib import Path

from tqdm import tqdm

from scripts.horadric_cube.constants import *
from scripts.horadric_cube.constants import CHRONO_JUMPER, WORKBENCH
from scripts.horadric_cube.db import load_default_databases
from scripts.horadric_cube.results import HoradricEngine
from scripts.horadric_cube.levels_and_pools import infer_ingredient_rarity, get_permanent_item_pool_bounded


def run_for_item_recipe(item, recipe, horadric_engine: HoradricEngine = None, explicit_ingredient_ids=None, min_avg_level=0, max_avg_level=100, print_summary=False, print_distribution=False, print_feasible_levels=False) -> None:
	if explicit_ingredient_ids is None:
		explicit_ingredient_ids = []

	if horadric_engine is None:
		horadric_engine = HoradricEngine.create_horadric_engine()

	# Example inventory: treat every item in the database as available once.
	inventory = {item_id: 10 for item_id in horadric_engine.item_db.items.keys()}

	item_data = horadric_engine.item_db.items[item]

	target_item_level = item_data.required_wave_level


	best_level, curve, avg_level_dist_map = horadric_engine.find_best_avg_level_for_item_with_inventory(
		target_item_id=item,
		recipe_id=recipe,
		inventory=inventory,
		avg_level_range=range(min_avg_level, max_avg_level),
		explicit_ingredient_ids=explicit_ingredient_ids,
	)

	if print_summary:
		print(f"Inventory-aware best avg ingredient level for item {item}: {best_level}")
		print("-" * 30)
		print(f"Explicit ingredients:")
		for item_id in explicit_ingredient_ids:
			ing_item_data = horadric_engine.item_db.items[item_id]
			print(f"Item ID: {ing_item_data.name_english}, with level {ing_item_data.required_wave_level}")
		print("-" * 30)
		if best_level is not None:
			print(f"Probability at best feasible level {best_level}: {curve[best_level]*100:.2f}%")

	# print the curve for feasible levels
	if print_feasible_levels:
		print("Feasible probabilities (non-zero) by level:")
		for level, prob in curve.items():
			if prob != 0:
				print("-" * 30)
				print(f"Level: {level}, probability for item {item_data.name_english} with level {target_item_level}: {prob*100:.2f}%")
				if print_distribution:
					print("+" * 30)
					avg_level_dist = avg_level_dist_map[level]
					# sort the distribution by probability
					avg_level_dist = sorted(avg_level_dist.items(), key=lambda x: x[1], reverse=True)
					for item_id, prob in avg_level_dist:
						dist_item_data = horadric_engine.item_db.items[item_id]
						print(f"Item ID: {dist_item_data.name_english}, with level {dist_item_data.required_wave_level} probability: {prob*100:.2f}%")
					print("+" * 30)

	if best_level is None:
		return None, None
	return best_level, curve[best_level]

def main() -> None:
	item = HAUNTED_HAND
	recipe = RECIPE_PERFECT

	horadric_engine = HoradricEngine.create_horadric_engine()

	recipe_num_items = horadric_engine.recipe_db.recipes[recipe].permanent_count

	run_for_item_recipe(item, recipe, horadric_engine, print_summary=True, print_feasible_levels=True, print_distribution=True)

	# item_level = horadric_engine.item_db.items[item].required_wave_level
	# ingredient_rarity = infer_ingredient_rarity(horadric_engine.item_db.items[item].rarity, horadric_engine.recipe_db.recipes[recipe])
	# base_best_level, base_probability = run_for_item_recipe(item, recipe, horadric_engine, explicit_ingredient_ids=[])
	# max_ingredient_level = item_level * (recipe_num_items + 1) - 1
	# ingredient_items = get_permanent_item_pool_bounded(horadric_engine.item_db, ingredient_rarity, 0, max_ingredient_level)
	# # sort ingredient items by level
	# ingredient_items = sorted(ingredient_items, key=lambda x: horadric_engine.item_db.items[x].required_wave_level)
	# ingredients_results_map = {}
	# for ingredient_item in tqdm(ingredient_items):
	#
	# 	best_level, probability = run_for_item_recipe(
	# 		item,
	# 		recipe,
	# 		horadric_engine,
	# 		explicit_ingredient_ids=[ingredient_item, ],
	# 		print_summary=False
	# 	)
	# 	if best_level is None:
	# 		continue
	# 	ing_key = (ingredient_item, )
	# 	ingredients_results_map[ing_key] = (best_level, probability)

		# ingredient_item_level = horadric_engine.item_db.items[ingredient_item].required_wave_level
		# ingredient_items2 = get_permanent_item_pool_bounded(horadric_engine.item_db, ingredient_rarity, ingredient_item_level, max_ingredient_level - ingredient_item_level)
		# # sort ingredient items2 by level
		# ingredient_items2 = sorted(ingredient_items2, key=lambda x: horadric_engine.item_db.items[x].required_wave_level)
		# for ingredient_item2 in ingredient_items2:
		# 	best_level, probability = run_for_item_recipe(
		# 		item,
		# 		recipe,
		# 		horadric_engine,
		# 		explicit_ingredient_ids=[ingredient_item, ingredient_item2],
		# 		print_summary=False
		# 	)
		# 	if best_level is None:
		# 		continue
		# 	ing_key = (ingredient_item, ingredient_item2)
		# 	ingredients_results_map[ing_key] = (best_level, probability)

	# highest probability
	# sorted_ingredients_results_map = sorted(ingredients_results_map.items(), key=lambda x: x[1][1], reverse=True)
	#
	# highest_probability_ings_key = sorted_ingredients_results_map[0][0]
	# highest_probability = ingredients_results_map[highest_probability_ings_key][1] * 100
	# best_level = ingredients_results_map[highest_probability_ings_key][0]
	# print(f"Highest probability: {highest_probability:.2f}%")
	# print(f"Best level: {best_level}")
	#
	# print(f"Ingredients: {highest_probability_ings_key}")
	#
	# # show all ties
	# print(f"All ingredients and best levels matching the highest probability of {highest_probability:.2f}%:")
	# idx = 0
	# same_value_epsilon = 0.01
	# while idx < len(sorted_ingredients_results_map):
	# 	ings_key = sorted_ingredients_results_map[idx][0]
	# 	probability = sorted_ingredients_results_map[idx][1][1] * 100
	# 	if probability < highest_probability - same_value_epsilon:
	# 		break
	# 	print(f"Ingredients: {ings_key}, Best level: {ingredients_results_map[ings_key][0]}, Probability: {probability:.2f}%")
	# 	idx += 1




if __name__ == "__main__":
	main()


