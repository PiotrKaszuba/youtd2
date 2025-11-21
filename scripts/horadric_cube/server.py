import http.server
import os
import pickle
import socketserver
import json
import sys
import threading
import time
import urllib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set, Sequence
from urllib import request

# Add the parent directory to sys.path so we can import from scripts
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from scripts.horadric_cube.results import HoradricEngine
from scripts.horadric_cube.optimizer import (
	OptimizerConfig,
	run_value_iteration,
	list_transmute_actions_for_state, _make_value_func, generate_candidate_sets_for_recipe, _compute_action_value,
)
from scripts.horadric_cube.constants import (
	USAGE_ITEM_VALUES,
	STRANGE_ITEM,
	GAME_PHASE,
	Inventory,
	get_game_phase_index, RECIPE_REASSEMBLE, RECIPE_PERFECT, GAME_PHASES, RUSTY_MINING_PICK, VOID_VIAL,
	ASSASINATION_ARROW, TRAINING_MANUAL, YOUNG_THIEF_CLOAK, SKULL_TROPHY, RING_OF_LUCK, SCARAB_AMULET, MAGIC_GLOVES,
	SPIDER_SILK, ORC_WAR_SPEAR, MAGICAL_ESSENCE, BOMB_SHELLS, NINJA_GLAIVE, SCROLL_OF_MYTHS, LAND_MINE,
)
from scripts.horadric_cube.models import Rarity

PORT = 8003

# Global engine and values, initialized on startup
engine: Optional[HoradricEngine] = None
item_values: Optional[Dict[int, Any]] = None
config: Optional[OptimizerConfig] = None

# file persistence
def save_item_values(item_values: Dict[int, Any]):
	with open("item_values.pkl", "wb") as f:
		pickle.dump(item_values, f)

def load_item_values():
	with open("item_values.pkl", "rb") as f:
		return pickle.load(f)

def initialize_engine():
	global engine, item_values, config
	print("Initializing Horadric Engine...", flush=True)
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
	config = OptimizerConfig(
		recipes_included={RECIPE_REASSEMBLE, RECIPE_PERFECT},
		excluded_recipe_rarities={(RECIPE_PERFECT, Rarity.UNIQUE), },

		ingredient_rarity_whitelist={Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE, Rarity.UNIQUE},
		phases_included={i for i in range(len(GAME_PHASES))},
		greedy_sets_per_recipe={-1: 1000},
		random_sets_per_recipe={-1: 100_000},
		num_iterations=50,
		learning_rate=0.15,
		strategies=["custom",],
		output_strategy="custom",
		percentile_target=97.5,
		custom_strategy_weights={
			"max": 0,
			"avg": 0.4,
			"pct": 0.6,
		},
	)

	item_values = load_item_values() if os.path.exists("item_values.pkl") else None
	if item_values is not None:
		print("Loaded item values from file", flush=True)
		# item_values = _update_item_values(item_values, usage_values_seed)
	else:
		print("Running initial value iteration...", flush=True)
		start_time = time.time()
		item_values = run_value_iteration(
			engine=engine,
			usage_values=usage_values_seed,
			config=config,
		)
		print(f"Value iteration complete in {time.time() - start_time:.2f}s")
		save_item_values(item_values)

def send_mock_client_request():
	"""
	Send a single mock optimization request to the locally running server.
	Useful for quick debugging without needing the game client.
	"""
	sample_request = {
		"request_id": "debug-1",
		"level": 1,
		"transmute_inventory_items": [
			# list of dicts: {"id": type_id, "uid": uid}
			{"id": RUSTY_MINING_PICK, "uid": 2},
			{"id": VOID_VIAL, "uid": 3},
			{"id": ASSASINATION_ARROW, "uid": 4},
			{"id": TRAINING_MANUAL, "uid": 5},
			{"id": YOUNG_THIEF_CLOAK, "uid": 6},
			{"id": SKULL_TROPHY, "uid": 7},
			{"id": RING_OF_LUCK, "uid": 8},
			{"id": SCARAB_AMULET, "uid": 9},
		],
		"tower_inventory": [
			# List[int]
			MAGIC_GLOVES,
			YOUNG_THIEF_CLOAK,
		],
	}

	data = json.dumps(sample_request).encode("utf-8")
	url = f"http://127.0.0.1:{PORT}/optimize"
	req = request.Request(
		url,
		data=data,
		headers={"Content-Type": "application/json", "Content-Length": str(len(data))},
		method="POST",
	)

	print(f"Mock client sending request to {url} ...", flush=True)
	try:
		with request.urlopen(req) as resp:
			body = resp.read().decode("utf-8")
			print("Mock client received response:", body, flush=True)
	except Exception as e:
		print(f"Mock client error: {e}", flush=True)


class OptimizationHandler(http.server.BaseHTTPRequestHandler):
	def log_message(self, format, *args):
		print("%s - - [%s] %s" %
			  (self.client_address[0],
			   self.log_date_time_string(),
			   format % args), flush=True)

	def do_POST(self):
		if self.path == '/optimize':
			content_length = int(self.headers['Content-Length'])
			post_data = self.rfile.read(content_length)
			
			try:
				data = json.loads(post_data.decode('utf-8'))
				response = self.process_optimization(data)
				
				response_bytes = json.dumps(response).encode('utf-8')
				
				self.send_response(200)
				self.send_header('Content-type', 'application/json')
				self.send_header('Content-Length', str(len(response_bytes)))
				self.end_headers()
				self.wfile.write(response_bytes)
			except Exception as e:
				print(f"Error processing request: {e}", flush=True)
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
		
		# Determine phase from level if provided
		level = int(data['level'])
		phase_idx = get_game_phase_index(level)

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

		actions: List[Tuple[int, List[int], float]] = []
		
		# Create a lightweight config for requests
		request_config = OptimizerConfig(
			recipes_included=config.recipes_included,
			excluded_recipe_rarities=config.excluded_recipe_rarities,
			ingredient_rarity_whitelist=config.ingredient_rarity_whitelist,
			phases_included={phase_idx},
			greedy_sets_per_recipe={-1: 100},
			random_sets_per_recipe={-1: 2000},
			output_strategy=config.output_strategy,
			percentile_target=config.percentile_target
		)
		
		value_func = _make_value_func(
			item_values=item_values,
			phase=phase_idx,
			state_inventory=inventory_for_caps,
		)

		for recipe in engine.recipe_db.recipes.values():
			recipe_id = recipe.id
			if request_config.recipes_included is not None and recipe_id not in request_config.recipes_included:
				continue

			# Use ACTIONS inventory (what we actually have in stash/cube) to generate candidates
			candidate_sets = generate_candidate_sets_for_recipe(
				engine=engine,
				recipe_id=recipe_id,
				phase=phase_idx,
				config=request_config,
				item_values=item_values,
				state_inventory=inventory_for_actions,
				value_func=value_func,
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
				# if delta <= 0.0:
				# 	continue
				actions.append((recipe_id, S, delta))

		actions.sort(key=lambda x: x[2], reverse=True)
		
		# performable_actions = []
		# for rid, S, delta in actions:
		# 	needed = {}
		# 	for item_id in S:
		# 		needed[item_id] = needed.get(item_id, 0) + 1
		#
		# 	possible = True
		# 	for item_id, count in needed.items():
		# 		if inventory_for_actions.get(item_id, 0) < count:
		# 			possible = False
		# 			break
		# 	if possible:
		# 		performable_actions.append((rid, S, delta))
		#
		# actions = performable_actions

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

		recipes_output = {}
		
		valid_actions_count = 0
		max_actions = 5 
		
		for rid, ingredients_type_ids, delta in actions:
			if valid_actions_count >= max_actions:
				break
				
			# Try to fulfill the ingredients using ONLY unused UIDs
			assigned_uids = []
			possible = True
			
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
				else:
					possible = False
					break
			
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
	print("Starting server script...", flush=True)
	initialize_engine()
	
	# Enable address reuse
	socketserver.TCPServer.allow_reuse_address = True
	
	# Use 0.0.0.0 to bind to all interfaces, ensuring we catch requests from localhost/127.0.0.1/::1
	with socketserver.TCPServer(("0.0.0.0", PORT), OptimizationHandler) as httpd:
		print(f"Serving at port {PORT}", flush=True)
		
		# If launched with --debug-client, spin up a background mock client
		# that sends a single request once the server is listening.
		if '--debug-client' in sys.argv or True:
			def _run_mock_client():
				# Small delay to ensure the server socket is ready
				time.sleep(1.0)
				send_mock_client_request()
			
			threading.Thread(target=_run_mock_client, daemon=True).start()
		
		httpd.serve_forever()
