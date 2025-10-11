class_name ReplayStateVerifier


# Verifies game state during replay by comparing hierarchical checksums.
# Reports any differences found during verification.


#########################
###       Public      ###
#########################

# Verify current game state against saved checkpoint
# Returns true if verification passed
static func verify_checkpoint(replay_id: String, tick: int) -> bool:
	var checkpoint_path: String = _get_checkpoint_path(replay_id, tick)
	
	if !FileAccess.file_exists(checkpoint_path):
		print("ReplayStateVerifier: Checkpoint file not found: ", checkpoint_path)
		return true  # Skip verification if file doesn't exist
	
	var file: FileAccess = FileAccess.open(checkpoint_path, FileAccess.READ)
	if file == null:
		push_error("ReplayStateVerifier: Failed to open checkpoint file: ", checkpoint_path)
		return false
	
	var json_text: String = file.get_as_text()
	file.close()
	
	var json: JSON = JSON.new()
	var parse_result: Error = json.parse(json_text)
	if parse_result != OK:
		push_error("ReplayStateVerifier: Failed to parse checkpoint JSON")
		return false
	
	var saved_tree: Dictionary = json.data
	
	# Build current state checksum tree
	var current_tree: Dictionary = ChecksumBuilder.build_checksum_tree(tick)
	
	# Compare trees
	var differences: Array = []
	_compare_trees(saved_tree, current_tree, "", differences)
	
	if differences.is_empty():
		print("ReplayStateVerifier: Checkpoint at tick %d PASSED" % tick)
		return true
	else:
		print("ReplayStateVerifier: Checkpoint at tick %d FAILED" % tick)
		_report_differences(differences)
		return false


#########################
###      Private      ###
#########################

static func _get_checkpoint_path(replay_id: String, tick: int) -> String:
	return "user://replays/_state/%s-%d.json" % [replay_id, tick]


# Recursively compare two checksum trees
static func _compare_trees(saved: Dictionary, current: Dictionary, path: String, differences: Array):
	# Compare root checksums
	var saved_checksum: String = saved.get("checksum", "")
	var current_checksum: String = current.get("checksum", "")
	
	if saved_checksum != current_checksum:
		differences.append({
			"path": path if !path.is_empty() else "root",
			"saved_checksum": saved_checksum,
			"current_checksum": current_checksum,
			"saved_data": saved.get("data", {}),
			"current_data": current.get("data", {}),
		})
		
		# If checksums differ, compare children to find source of difference
		if saved.has("children") && current.has("children"):
			var saved_children: Dictionary = saved["children"]
			var current_children: Dictionary = current["children"]
			
			# Get all keys from both trees
			var all_keys: Dictionary = {}
			for key in saved_children.keys():
				all_keys[key] = true
			for key in current_children.keys():
				all_keys[key] = true
			
			for key in all_keys.keys():
				var child_path: String = path + "/" + key if !path.is_empty() else key
				
				if !saved_children.has(key):
					differences.append({
						"path": child_path,
						"error": "Missing in saved state (exists in current)",
					})
				elif !current_children.has(key):
					differences.append({
						"path": child_path,
						"error": "Missing in current state (exists in saved)",
					})
				else:
					_compare_trees(saved_children[key], current_children[key], child_path, differences)


static func _report_differences(differences: Array):
	print("=== REPLAY VERIFICATION FAILED ===")
	print("Found %d differences:" % differences.size())
	print("")
	
	for diff in differences:
		var path: String = diff.get("path", "unknown")
		print("Path: %s" % path)
		
		if diff.has("error"):
			print("  Error: %s" % diff["error"])
		else:
			var saved_checksum: String = diff.get("saved_checksum", "")
			var current_checksum: String = diff.get("current_checksum", "")
			print("  Saved checksum:   %s" % saved_checksum)
			print("  Current checksum: %s" % current_checksum)
			
			var saved_data: Dictionary = diff.get("saved_data", {})
			var current_data: Dictionary = diff.get("current_data", {})
			
			if !saved_data.is_empty() || !current_data.is_empty():
				print("  Saved data:   %s" % JSON.stringify(saved_data))
				print("  Current data: %s" % JSON.stringify(current_data))
		
		print("")
	
	print("=== END VERIFICATION REPORT ===")
	
	# Also add message to local player if available
	var local_player: Player = PlayerManager.get_local_player()
	if local_player != null:
		Messages.add_error(local_player, "Replay verification failed! Check console for details.")

