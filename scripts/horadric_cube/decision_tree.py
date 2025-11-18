from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Union

import numpy as np


@dataclass
class DecisionNode:
	"""
	Represents a random decision point.

	- name: semantic label for this decision (e.g. "luck", "item_choice").
	- probabilities: numpy array of shape (n,) summing to 1.
	- outcomes: list of either item IDs (int) or nested DecisionNode instances.
	"""

	name: str
	probabilities: np.ndarray
	outcomes: List[Union[int, "DecisionNode"]]

	def __post_init__(self) -> None:
		if len(self.probabilities) != len(self.outcomes):
			raise ValueError("probabilities and outcomes must have the same length")
		total = float(self.probabilities.sum())
		if total <= 0:
			raise ValueError("probabilities must sum to > 0")
		self.probabilities = self.probabilities / total

	def roll(self, rng: np.random.Generator) -> Union[int, "DecisionNode"]:
		"""
		Randomly pick a single outcome according to probabilities.
		"""
		index = int(rng.choice(len(self.outcomes), p=self.probabilities))
		return self.outcomes[index]

	def roll_to_item(self, rng: np.random.Generator) -> int:
		"""
		Recursively roll until an item ID (int) is reached.
		"""
		outcome = self.roll(rng)
		if isinstance(outcome, DecisionNode):
			return outcome.roll_to_item(rng)
		return int(outcome)


def collapse_to_item_distribution(node: DecisionNode) -> Dict[int, float]:
	"""
	Traverse a decision tree and produce a flat distribution over item IDs.
	Probabilities along the path are multiplied; items reached by multiple
	paths have their probabilities summed.
	"""
	result: Dict[int, float] = {}

	def _walk(current_node: DecisionNode, weight: float) -> None:
		for prob, outcome in zip(current_node.probabilities, current_node.outcomes):
			new_weight = weight * float(prob)
			if isinstance(outcome, DecisionNode):
				_walk(outcome, new_weight)
			else:
				item_id = int(outcome)
				result[item_id] = result.get(item_id, 0.0) + new_weight

	_walk(node, 1.0)
	return result


LUCK_VALUES = np.array([-9, 0, 7, 18], dtype=int)
LUCK_WEIGHTS = np.array([20.0, 50.0, 20.0, 10.0], dtype=float)


def build_luck_node(name: str = "luck") -> DecisionNode:
	"""
	Luck decision as in HoradricCube._get_random_bonus_mod.
	"""
	probabilities = LUCK_WEIGHTS.copy()
	outcomes: List[int] = [int(v) for v in LUCK_VALUES]
	return DecisionNode(name=name, probabilities=probabilities, outcomes=outcomes)


def build_item_choice_node(
	item_ids: List[int],
	name: str = "item_choice",
) -> DecisionNode:
	"""
	Uniform item choice among the given IDs.
	"""
	if not item_ids:
		raise ValueError("item_ids must not be empty")
	n = len(item_ids)
	probabilities = np.full(shape=(n,), fill_value=1.0 / n, dtype=float)
	outcomes = [int(i) for i in item_ids]
	return DecisionNode(name=name, probabilities=probabilities, outcomes=outcomes)


