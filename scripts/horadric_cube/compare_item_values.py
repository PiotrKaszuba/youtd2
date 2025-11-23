"""Utility script to compare two serialized item value tables."""

from __future__ import annotations

import argparse
import pickle
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
	sys.path.append(str(ROOT_DIR))

from scripts.horadric_cube.constants import GAME_PHASES, ItemValue
from scripts.horadric_cube.db import ItemDatabase
from scripts.horadric_cube.models import Rarity

ItemValues = Dict[int, ItemValue]


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Compare two item_values.pkl files and print a formatted NumPy table.",
	)
	parser.add_argument("file_a", type=Path, help="Path to the baseline item_values.pkl file.")
	parser.add_argument("file_b", type=Path, help="Path to the new item_values.pkl file.")
	parser.add_argument(
		"--phase",
		type=int,
		default=None,
		choices=range(len(GAME_PHASES)),
		metavar=f"[0-{len(GAME_PHASES)-1}]",
		help=(
			"Phase index to inspect. Defaults to listing all phases when omitted."
		),
	)
	parser.add_argument(
		"--item-ids",
		type=int,
		nargs="+",
		default=None,
		metavar="ITEM_ID",
		help="Restrict the comparison to the provided item IDs (order is preserved).",
	)

	args = parser.parse_args()
	args.file_a = args.file_a.expanduser().resolve()
	args.file_b = args.file_b.expanduser().resolve()

	for path in (args.file_a, args.file_b):
		if not path.exists():
			parser.error(f"File not found: {path}")

	return args


def load_item_values(path: Path) -> ItemValues:
	with path.open("rb") as fp:
		return pickle.load(fp)


_ITEM_DB: Optional[ItemDatabase] = None


def get_item_database() -> ItemDatabase:
	global _ITEM_DB
	if _ITEM_DB is None:
		_ITEM_DB = ItemDatabase._load_default_database()
	return _ITEM_DB


def resolve_item_name(item_id: int, item_db: ItemDatabase) -> str:
	item = item_db.items.get(int(item_id))
	if item and item.name_english:
		return item.name_english
	if item and item.name:
		return item.name
	return f"Item {item_id}"


def extract_scalar_value(
	item_value: Optional[ItemValue],
	attr: str,
	phase: int,
) -> float:
	if item_value is None:
		return float("nan")

	value_map = getattr(item_value, attr, None)
	if not value_map:
		return float("nan")

	return float(value_map.get(phase, 0.0))


def round_three_places(value: float) -> float:
	if isinstance(value, float) and np.isnan(value):
		return value
	return float(np.round(value, 3))


def build_rows_by_rarity(
	item_ids: Sequence[int],
	values_a: ItemValues,
	values_b: ItemValues,
	item_db: ItemDatabase,
	phases: Sequence[int],
	preserve_order: bool = False,
) -> Dict[Optional[int], List[Tuple[str, int, float, float, float, float]]]:
	rows_by_rarity: Dict[Optional[int], List[Tuple[str, int, float, float, float, float]]] = defaultdict(list)

	for item_id in item_ids:
		name = resolve_item_name(item_id, item_db)
		item = item_db.items.get(int(item_id))
		rarity = item.rarity if item is not None else None

		for phase in phases:
			usage_a = round_three_places(
				extract_scalar_value(values_a.get(item_id), "usage_value", phase)
			)
			usage_b = round_three_places(
				extract_scalar_value(values_b.get(item_id), "usage_value", phase)
			)
			transmute_a = round_three_places(
				extract_scalar_value(values_a.get(item_id), "transmute_value", phase)
			)
			transmute_b = round_three_places(
				extract_scalar_value(values_b.get(item_id), "transmute_value", phase)
			)

			rows_by_rarity[rarity].append((name, phase, usage_a, usage_b, transmute_a, transmute_b))

	if not preserve_order:
		for rows in rows_by_rarity.values():
			rows.sort(key=lambda row: (row[0].lower(), row[1], row[0]))

	return rows_by_rarity


def rows_to_numpy(rows: Sequence[Tuple[str, int, float, float, float, float]]) -> np.ndarray:
	if not rows:
		return np.empty((0, 6), dtype=object)

	return np.array(rows, dtype=object)


def append_delta_column(array: np.ndarray) -> np.ndarray:
	if array.size == 0:
		return array

	result = np.empty((array.shape[0], array.shape[1] + 1), dtype=object)
	result[:, :-1] = array
	result[:, -1] = result[:, -2] - result[:, -3]
	return result


def sort_by_delta(array: np.ndarray) -> np.ndarray:
	if array.size == 0:
		return array
	return array[np.argsort(np.abs(array[:, -1]))]


def format_array(array: np.ndarray) -> str:
	if array.size == 0:
		return "[]"

	def _format_object(value: object) -> str:
		if isinstance(value, (float, np.floating)):
			if np.isnan(value):
				return "nan"
			return f"{value:.3f}"
		return str(value)

	return np.array2string(array, formatter={"object": _format_object}, max_line_width=160)


def phase_label(phase: Optional[int]) -> str:
	if phase is None:
		return "all phases"
	return f"{phase}"


def rarity_label(rarity: Optional[int]) -> str:
	if rarity is None:
		return "unknown"
	return Rarity.to_string(int(rarity))


def rarity_sort_key(rarity: Optional[int]) -> Tuple[int, int]:
	if rarity is None:
		return (1, sys.maxsize)
	return (0, int(rarity))


def resolve_phases(phase: Optional[int]) -> List[int]:
	if phase is not None:
		return [phase]
	return list(range(len(GAME_PHASES)))


def determine_item_ids(
	values_a: ItemValues,
	values_b: ItemValues,
	requested_ids: Optional[Sequence[int]],
) -> List[int]:
	if requested_ids:
		seen: List[int] = []
		for raw_id in requested_ids:
			item_id = int(raw_id)
			if item_id not in seen:
				seen.append(item_id)
		return seen

	return sorted(set(values_a.keys()) | set(values_b.keys()))


def main() -> None:
	args = parse_args()
	values_a = load_item_values(args.file_a)
	values_b = load_item_values(args.file_b)
	item_db = get_item_database()

	phases = resolve_phases(args.phase)
	item_ids = determine_item_ids(values_a, values_b, args.item_ids)
	rows_by_rarity = build_rows_by_rarity(
		item_ids,
		values_a,
		values_b,
		item_db,
		phases,
		preserve_order=bool(args.item_ids),
	)

	print(f"Comparing '{args.file_a}' vs '{args.file_b}' (phase={phase_label(args.phase)})")
	np.set_printoptions(threshold=np.inf)

	for rarity in sorted(rows_by_rarity.keys(), key=rarity_sort_key):
		rows = rows_by_rarity[rarity]
		array = rows_to_numpy(rows)
		array = append_delta_column(array)
		array = sort_by_delta(array)

		print(f"[rarity={rarity_label(rarity)} | rows={len(rows)}]")
		print(format_array(array))


if __name__ == "__main__":
	main()

