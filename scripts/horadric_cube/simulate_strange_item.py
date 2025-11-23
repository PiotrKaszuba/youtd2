from typing import Dict, Any
from collections import Counter
from scripts.horadric_cube.constants import GAME_PHASES, get_phase_level_bounds, GAME_PHASE, get_game_phase_index, \
	STRANGE_ITEM, get_phase_avg_level


def strange_item_count_from_level_to_level(level_start: int, level_stop: int, copy_every: int, stop_at: int) -> Counter:
	count_per_phase = Counter()
	count_per_phase[get_game_phase_index(level_start)] = 1
	if copy_every >= stop_at:
		return count_per_phase

	
	for level in range(level_start, level_stop, copy_every):
		count_from_generation = strange_item_count_from_level_to_level(level, level_stop, copy_every + 6, stop_at)
		count_per_phase += count_from_generation
	
	return count_per_phase


def strange_item_per_phase_count(level_stop: int, stop_at: int) -> Dict[GAME_PHASE, Counter]:
	count_per_phase_start_at = {}
	for game_phase in range(len(GAME_PHASES)):
		lvl_avg = get_phase_avg_level(game_phase)
		count = strange_item_count_from_level_to_level(lvl_avg, level_stop, 12, stop_at)
		count[game_phase] -= 1
		count_per_phase_start_at[game_phase] = count

	return count_per_phase_start_at


def strange_item_per_phase_usage_from_transmute_values(
	transmute_values: Dict[int, float],
	level_stop: int,
	stop_at: int,
	per_level_discount_factor: float = 0.999
) -> Dict[GAME_PHASE, float]:
	count_per_phase = strange_item_per_phase_count(level_stop, stop_at)
	usage_vals = {}

	for game_phase in range(len(GAME_PHASES)):
		usage_val = 0
		avg_phase_level = get_phase_avg_level(game_phase)
		for phase_cnt_idx, phase_cnt in count_per_phase[game_phase].items():
			avg_result_phase_level = get_phase_avg_level(phase_cnt_idx)
			level_diff = avg_result_phase_level - avg_phase_level
			if level_diff < 0:
				continue
			discount_factor = per_level_discount_factor ** level_diff
			usage_val += phase_cnt * transmute_values.get(phase_cnt_idx, 0.0) * discount_factor
		usage_vals[game_phase] = usage_val

	return usage_vals


def strange_item_per_phase_usage_val(item_values: Dict[int, Any], level_stop: int, stop_at: int, per_level_discount_factor: float = 0.999) -> Dict[GAME_PHASE, float]:
	transmute_values = item_values[STRANGE_ITEM].transmute_value
	return strange_item_per_phase_usage_from_transmute_values(transmute_values, level_stop, stop_at, per_level_discount_factor)


def strange_item_usage_from_T_table(
	T_table: Dict[int, Dict[GAME_PHASE, float]],
	level_stop: int,
	stop_at: int,
	per_level_discount_factor: float = 0.999,
) -> Dict[GAME_PHASE, float]:
	strange_transmute_values = {phase_idx: T_table.get(STRANGE_ITEM, {}).get(phase_idx, 0.0) for phase_idx in range(len(GAME_PHASES))}
	return strange_item_per_phase_usage_from_transmute_values(strange_transmute_values, level_stop, stop_at, per_level_discount_factor)


if __name__ == "__main__":
	res = strange_item_per_phase_count(300, 24)

	for k,v in res.items():
		print(k, v, (sum(res[k].values())))
	# print(strange_item_per_phase_count(350, 30))
