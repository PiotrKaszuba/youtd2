from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict
import numpy as np

class ValueStrategy(ABC):
	"""
	Abstract base class for value calculation strategies.
	"""
	@abstractmethod
	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		"""
		Calculate the next value for an item based on a list of candidate values
		(one for each valid recipe/permutation).
		
		current_value: The item's value from the previous iteration (or initialization).
		candidate_values: A list of potential new values derived from recipes. 
						  If empty, typically implies no transmute gain is possible.
		"""
		pass

class MaxStrategy(ValueStrategy):
	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		if not candidate_values:
			return current_value
		return max(current_value, max(candidate_values))

class AvgStrategy(ValueStrategy):
	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		if not candidate_values:
			return current_value
		# We include the current value as a baseline or "do nothing" option? 
		# Usually transmute value is "what can I get via transmuting".
		# If we take avg of recipes, do we include the option of "not transmuting"?
		# The original logic was T[item] = (1-alpha)*old + alpha * best_candidate.
		# Here we are calculating the 'target' value that alpha will move towards, 
		# OR we are defining the aggregation of candidates.
		# The prompt says: "avg of recipes".
		return float(np.mean(candidate_values))

class PercentileStrategy(ValueStrategy):
	def __init__(self, percentile: float = 85.0):
		self.percentile = percentile

	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		if not candidate_values:
			return current_value
		return float(np.percentile(candidate_values, self.percentile))

class CustomStrategy(ValueStrategy):
	"""
	A strategy that aggregates results from other strategies.
	Note: This one assumes it receives the *results* of other strategies, 
	not raw candidate values. But the interface expects candidate_values.
	
	The user specified: "default is sum of previous tables/3 in current iteration".
	This implies CustomStrategy is a meta-strategy.
	
	We'll handle the specific logic for CustomStrategy in the optimizer loop 
	because it depends on the outputs of other strategies, not just raw candidates.
	
	However, to fit the interface, we might need to adapt or handle it specially.
	For now, I'll implement a placeholder or helper, but the real logic will likely 
	live in the multi-strategy evaluation loop.
	"""
	def calculate_next_value(self, current_value: float, candidate_values: List[float]) -> float:
		# This method might not be used for CustomStrategy in the same way.
		# But if we strictly followed the prompt "custom value table based on previous ones",
		# it suggests it doesn't look at candidates directly.
		return current_value

STRATEGY_MAP = {
	"max": MaxStrategy,
	"avg": AvgStrategy,
	"percentile": PercentileStrategy,
	"custom": CustomStrategy,
}

