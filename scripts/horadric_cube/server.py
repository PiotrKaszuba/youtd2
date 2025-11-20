import http.server
import socketserver
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add the parent directory to sys.path so we can import from scripts
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from scripts.horadric_cube.results import HoradricEngine
from scripts.horadric_cube.optimizer import (
	OptimizerConfig,
	run_value_iteration,
	list_transmute_actions_for_state,
)
from scripts.horadric_cube.constants import (
	USAGE_ITEM_VALUES,
	STRANGE_ITEM,
	GAME_PHASE,
	Inventory,
	get_game_phase_index,
)
from scripts.horadric_cube.models import Rarity

PORT = 8000

# Global engine and values, initialized on startup
engine: Optional[HoradricEngine] = None
item_values: Optional[Dict[int, Any]] = None
config: Optional[OptimizerConfig] = None

def initialize_engine():
	global engine, item_values, config
	print("Initializing Horadric Engine...")
	engine = HoradricEngine.create_horadric_engine()
	
	# Filter items as in the demo
	engine.item_db = engine.item_db.filter_items(
		level_min=0,
		level_max=1000,
		rarity_whitelist={Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE, Rarity.UNIQUE},
	)

	# Use usage values from constants
	usage_values_seed = dict(USAGE_ITEM_VALUES)
	
	# Default config
	phase = 5 # Default phase if not specified
	config = OptimizerConfig(
		ingredient_rarity_whitelist={Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE, Rarity.UNIQUE},
		phases_included={phase},
		greedy_sets_per_recipe={-1: 500},
		random_sets_per_recipe={-1: 20000},
		num_iterations=30,
		learning_rate=0.2,
		strategies=["max", "avg", "percentile", "custom"],
		output_strategy="percentile",
		percentile_target=98.0,
	)

	print("Running initial value iteration...")
	start_time = time.time()
	item_values = run_value_iteration(
		engine=engine,
		usage_values=usage_values_seed,
		config=config,
	)
	print(f"Value iteration complete in {time.time() - start_time:.2f}s")

class OptimizationHandler(http.server.BaseHTTPRequestHandler):
	def do_POST(self):
		if self.path == '/optimize':
			content_length = int(self.headers['Content-Length'])
			post_data = self.rfile.read(content_length)
			
			try:
				data = json.loads(post_data.decode('utf-8'))
				response = self.process_optimization(data)
				
				self.send_response(200)
				self.send_header('Content-type', 'application/json')
				self.end_headers()
				self.wfile.write(json.dumps(response).encode('utf-8'))
			except Exception as e:
				print(f"Error processing request: {e}")
				self.send_response(500)
				self.end_headers()
				self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
		else:
			self.send_response(404)
			self.end_headers()

	def process_optimization(self, data: Dict[str, Any]) -> Dict[str, Any]:
		request_id = data.get('request_id')
		# Expecting list of dicts: [{'id': type_id, 'uid': uid}, ...]
		transmute_inventory_items = data.get('transmute_inventory_items', [])
		tower_inventory_ids = data.get('tower_inventory', [])
		
		# Determine phase from level if provided, otherwise use explicit phase or default
		if 'level' in data:
			level = int(data['level'])
			phase_idx = get_game_phase_index(level)
		else:
			phase_idx = data.get('phase', 5)

		# Helper to convert item list to Inventory (counts of Type IDs)
		def items_to_inventory(items: List[Dict[str, int]]) -> Inventory:
			inv = {}
			for item in items:
				tid = item['id']
				inv[tid] = inv.get(tid, 0) + 1
			return inv

		# Helper to convert ID list to Inventory
		def ids_to_inventory(ids: List[int]) -> Inventory:
			inv = {}
			for i in ids:
				inv[i] = inv.get(i, 0) + 1
			return inv

		inventory_for_actions = items_to_inventory(transmute_inventory_items)
		
		# Combine inventories for caps: counts from transmute items + counts from tower IDs
		inventory_for_caps = items_to_inventory(transmute_inventory_items)
		tower_counts = ids_to_inventory(tower_inventory_ids)
		for tid, count in tower_counts.items():
			inventory_for_caps[tid] = inventory_for_caps.get(tid, 0) + count

		# Temporarily update item values context with the full inventory for caps logic
		# Note: run_value_iteration produced `item_values` which are "Global" values.
		# Ideally we would use run_state_local_refinement here if we wanted to react 
		# to caps strictly, but for speed we can pass the inventory_for_caps 
		# when creating the context for scoring.
		
		# However, `list_transmute_actions_for_state` takes `state_inventory` and uses it 
		# both for availability checks AND potentially for value function context if implemented so.
		# In the current optimizer implementation:
		# list_transmute_actions_for_state -> _make_value_func(item_values, ..., state_inventory)
		#
		# _make_value_func uses state_inventory to check caps.
		# So we want `inventory_for_caps` to be passed as `state_inventory` for value calculation purposes,
		# BUT we want `inventory_for_actions` to be used for `generate_candidate_sets_for_recipe`.
		
		# The current `list_transmute_actions_for_state` signature is:
		# (engine, item_values, state_inventory, ...)
		# It uses `state_inventory` for both.
		
		# To support the split without modifying optimizer.py too much, we can:
		# Manually run the steps inside list_transmute_actions_for_state here.
		
		actions: List[Tuple[int, List[int], float]] = []
		
		# This value function uses the CAPS inventory to determine item worth
		# (e.g. if we have too many of item X on towers + stash, its value drops)
		from scripts.horadric_cube.optimizer import _make_value_func, generate_candidate_sets_for_recipe, _compute_action_value
		
		value_func = _make_value_func(
			item_values=item_values,
			phase=phase_idx,
			state_inventory=inventory_for_caps, 
		)

		for recipe in engine.recipe_db.recipes.values():
			recipe_id = recipe.id
			if config.recipes_included is not None and recipe_id not in config.recipes_included:
				continue

			# Use ACTIONS inventory (what we actually have in stash/cube) to generate candidates
			candidate_sets = generate_candidate_sets_for_recipe(
				engine=engine,
				recipe_id=recipe_id,
				phase=phase_idx,
				config=config,
				item_values=item_values,
				state_inventory=inventory_for_actions, 
			)

			for S in candidate_sets:
				if not S:
					continue
				_, delta = _compute_action_value(
					engine=engine,
					recipe=recipe,
					S=S,
					phase=phase_idx,
					value_func=value_func,
				)
				if delta > 0.0:
					actions.append((recipe_id, S, delta))

		actions.sort(key=lambda x: x[2], reverse=True)

		# Global tracking of used UIDs to ensure suggested recipes are non-overlapping
		global_used_uids: Set[int] = set()
		
		# Optimization: index available items by ID
		items_by_id: Dict[int, List[int]] = {}
		for item in transmute_inventory_items:
			tid = item['id']
			uid = item['uid']
			if tid not in items_by_id:
				items_by_id[tid] = []
			items_by_id[tid].append(uid)

		# List of final suggested recipes (flat list of dicts) or grouped?
		# The original format was by recipe ID.
		# But now we want a SET of compatible actions.
		# Let's still return them grouped by recipe ID for UI consistency, 
		# but ensure that if user executes Action A, Action B is still valid (or was valid at generation time).
		
		recipes_output = {}
		
		valid_actions_count = 0
		max_actions = 5 # Total number of actions to suggest across ALL recipes? Or per recipe?
		# User requested: "return a set of K (5?) recipes that ALL can be executed together"
		
		for rid, ingredients_type_ids, delta in actions:
			if valid_actions_count >= max_actions:
				break
				
			# Try to fulfill the ingredients using ONLY unused UIDs
			assigned_uids = []
			possible = True
			
			# We need to pick specific UIDs for this action
			# To be deterministic and optimal, we should probably pick UIDs that are 
			# "least valuable" elsewhere? Or just any valid UID?
			# For now, just pick first available that is not in global_used_uids
			
			for tid in ingredients_type_ids:
				tid = int(tid)
				if tid not in items_by_id:
					possible = False
					break
				
				found_uid = None
				for candidate_uid in items_by_id[tid]:
					if candidate_uid not in global_used_uids:
						found_uid = candidate_uid
						break
				
				if found_uid is not None:
					assigned_uids.append(found_uid)
					# Temporarily mark as used for this action check
					# (We will commit to global_used_uids only if whole action is possible)
				else:
					possible = False
					break
			
			# Double check distinctness within action (already handled by global check logic effectively, 
			# but ingredients_type_ids could have duplicates of same type)
			# The loop above picks *one* candidate. If we need 2 of Type A, 
			# we need to pick 2 DIFFERENT candidates.
			# The simple loop above might pick the SAME candidate twice if we don't exclude it immediately.
			
			# Refined allocation for this action:
			if possible:
				# Re-verify with strict consumption tracking for this specific action
				current_action_uids = []
				temp_used = set()
				
				for tid in ingredients_type_ids:
					tid = int(tid)
					found_uid = None
					if tid in items_by_id:
						for candidate_uid in items_by_id[tid]:
							if candidate_uid not in global_used_uids and candidate_uid not in temp_used:
								found_uid = candidate_uid
								break
					
					if found_uid is not None:
						current_action_uids.append(found_uid)
						temp_used.add(found_uid)
					else:
						possible = False
						break
				
				if possible:
					# Commit this action
					global_used_uids.update(temp_used)
					valid_actions_count += 1
					
					if rid not in recipes_output:
						recipe_def = engine.recipe_db.recipes[rid]
						recipes_output[rid] = {
							"id": rid,
							"name": recipe_def.name_english if recipe_def.name_english else recipe_def.display_name,
							"actions": []
						}
					
					recipes_output[rid]["actions"].append({
						"ingredients": current_action_uids,
						"gain": float(delta)
					})

		return {"recipes": list(recipes_output.values()), "request_id": request_id}

if __name__ == '__main__':
	initialize_engine()
	with socketserver.TCPServer(("", PORT), OptimizationHandler) as httpd:
		print(f"Serving at port {PORT}")
		httpd.serve_forever()

