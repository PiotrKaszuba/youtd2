class_name GameStateSnapshotBuilder
extends RefCounted

func build(current_tick: int) -> SnapshotNode:
        var root := SnapshotNode.new("game_state")
        root.add_field("tick", current_tick)
        _append_globals(root)
        _append_rng(root)
        _append_world(root)
        _append_players(root)
        _append_teams(root)
        return root

func _append_globals(root: SnapshotNode) -> void:
        var globals_node := root.create_child("globals")
        globals_node.add_field("origin_seed", Globals.get_origin_seed())
        globals_node.add_field("player_mode", _player_mode_to_string(Globals.get_player_mode()))
        globals_node.add_field("game_mode", GameMode.convert_to_string(Globals.get_game_mode()))
        globals_node.add_field("difficulty", Difficulty.convert_to_string(Globals.get_difficulty()))
        globals_node.add_field("team_mode", TeamMode.convert_to_string(Globals.get_team_mode()))
        globals_node.add_field("wave_count", Globals.get_wave_count())
        globals_node.add_field("update_ticks_per_physics_tick", Globals.get_update_ticks_per_physics_tick())
        globals_node.add_field("connection_type", _connection_type_to_string(Globals.get_connect_type()))

        var map: Map = Globals.get_map()
        if map != null:
                globals_node.add_field("map_name", map.name)
                globals_node.add_field("map_scene", map.scene_file_path)

func _append_rng(root: SnapshotNode) -> void:
        var rng_node := root.create_child("rng")
        var rng: RandomNumberGenerator = Globals.synced_rng
        rng_node.add_field("seed", rng.get_seed())

        if rng.has_method("get_state"):
                rng_node.add_field("state", rng.get_state())
        if rng.has_method("get_position"):
                rng_node.add_field("position", rng.get_position())
        if rng.has_method("get_call_count"):
                rng_node.add_field("call_count", rng.get_call_count())

func _append_players(root: SnapshotNode) -> void:
        var players_node := root.create_child("players")
        var player_list: Array[Player] = PlayerManager.get_player_list()
        player_list.sort_custom(func(a: Player, b: Player): return a.get_id() < b.get_id())

        for player in player_list:
                var player_node := players_node.create_child("player_%d" % player.get_id())
                player.build_snapshot(player_node)

func _append_world(root: SnapshotNode) -> void:
        var world_node := root.create_child("world")
        var tower_list: Array[Tower] = Utils.get_tower_list()
        var creep_list: Array[Creep] = Utils.get_creep_list()
        var tree := Engine.get_main_loop() as SceneTree
        var projectile_list: Array = []
        var timer_list: Array = []

        if tree != null:
                projectile_list = tree.get_nodes_in_group("projectiles")
                timer_list = tree.get_nodes_in_group("manual_timers")

        world_node.add_field("tower_count", tower_list.size())
        world_node.add_field("creep_count", creep_list.size())
        world_node.add_field("projectile_count", projectile_list.size())
        world_node.add_field("manual_timer_count", timer_list.size())

func _append_teams(root: SnapshotNode) -> void:
        var teams_node := root.create_child("teams")
        var team_map: Dictionary = {}

        var player_list: Array[Player] = PlayerManager.get_player_list()
        for player in player_list:
                var team: Team = player.get_team()
                if team == null:
                        continue
                team_map[team.get_id()] = team

        var team_ids: Array = team_map.keys()
        team_ids.sort()

        for team_id in team_ids:
                var team: Team = team_map[team_id]
                var team_node := teams_node.create_child("team_%d" % team_id)
                team.build_snapshot(team_node)

func _player_mode_to_string(mode: PlayerMode.enm) -> String:
        match mode:
                PlayerMode.enm.SINGLEPLAYER:
                        return "singleplayer"
                PlayerMode.enm.MULTIPLAYER:
                        return "multiplayer"
                _:
                        return str(mode)

func _connection_type_to_string(connection_type: Globals.ConnectionType) -> String:
        match connection_type:
                Globals.ConnectionType.ENET:
                        return "enet"
                Globals.ConnectionType.NAKAMA:
                        return "nakama"
                _:
                        return str(connection_type)
