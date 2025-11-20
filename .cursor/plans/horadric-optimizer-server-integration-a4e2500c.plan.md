<!-- a4e2500c-6d35-4b0e-a69b-c66f9f473163 4d32eaa6-cbee-4819-a295-099b1dd1d436 -->
# Plan: Horadric Cube Optimizer Server & UI Integration

This plan implements a "Smart Ask" feature where the game queries a local Python server for optimal Horadric Cube recipes. The UI features a toggle button (Ask/Clear) and handles responses asynchronously.

## 1. Python Server (`scripts/horadric_cube/server.py`)

Create a standalone Python HTTP server using `http.server`.

- **Startup**:
    - Initialize `HoradricEngine`.
    - Run `run_value_iteration` (approx 30 iters) with default config/usage values to learn item values.
- **Endpoint**: `POST /optimize`
    - **Input**: JSON `{"transmute_inventory": [id1, ...], "tower_inventory": [id1, ...], "phase": 5}`.
    - **Logic**:
        - `inventory_for_caps` = counts(`transmute_inventory` + `tower_inventory`).
        - `inventory_for_actions` = counts(`transmute_inventory`).
        - Initialize `ItemValue`s using `inventory_for_caps` (so usage caps account for items on towers).
        - Call `list_transmute_actions_for_state` using `inventory_for_actions` (only suggest using items actually available for transmute).
        - Select top 5 actions per recipe.
    - **Output**: JSON `{"recipes": [{"name": "Recipe Name", "actions": [{"ingredients": [id, ...], "gain": 1.5}, ...]}, ...]}`.

## 2. Event Bus & Game Logic

- **`src/singletons/event_bus.gd`**:
    - Add signal `player_requested_specific_autofill(item_uid_list: Array[int])`.
- **`src/game_scene/game_scene.gd`**:
    - Connect `player_requested_specific_autofill` to a handler.
    - Handler calls `ActionAutofill.make(item_uid_list)` and adds it to `_game_client`.

## 3. UI Implementation (`src/ui/item_stash_menu/`)

- **`item_stash_menu.tscn`**:
    - Add `OptimizerButton` to `HoradricPanel`.
    - Add a `ScrollContainer` + `VBoxContainer` (hidden by default) for results.
    - Add an `HTTPRequest` node.
    - Add a `Timer` node for request timeout (e.g., 5s).
- **`item_stash_menu.gd`**:
    - **State Management**: `enum State { IDLE, WAITING, RESULTS }`.
    - **`_on_optimizer_button_pressed`**:
        - **If IDLE**:
            - Gather `transmute_inventory` (stash + cube) and `tower_inventory` (player's towers).
            - Convert to ID lists.
            - Send POST to server.
            - Set State = WAITING (Icon: Clear/Cancel). Start Timer.
        - **If WAITING**:
            - Cancel request (abort `HTTPRequest` or set flag to ignore response).
            - Set State = IDLE (Icon: Ask). Stop Timer.
        - **If RESULTS**:
            - Clear result buttons.
            - Set State = IDLE (Icon: Ask).
    - **`_on_request_completed`**:
        - If State != WAITING (cancelled): Return.
        - Parse JSON. Display buttons.
        - Set State = RESULTS (Icon: Clear).
    - **`_on_timeout`**:
        - If State == WAITING: Set State = IDLE. Cancel request.
    - **`_on_suggestion_pressed(required_item_ids)`**:
        - Greedy match `required_item_ids` against local `Item` instances (UIDs) in stash/cube.
        - If found: Emit `EventBus.player_requested_specific_autofill(uids)`.
        - Else: Show UI error.

## 4. Helper Scripts

- **`scripts/run_horadric_server.py`**: Wrapper to launch the server module.

### To-dos

- [ ] Create Python server script `scripts/horadric_cube/server.py`
- [ ] Add `player_requested_specific_autofill` to `src/singletons/event_bus.gd`
- [ ] Handle specific autofill in `src/game_scene/game_scene.gd`
- [ ] Add Smart Ask button and results container to `src/ui/item_stash_menu/item_stash_menu.tscn`
- [ ] Implement request and response logic in `src/ui/item_stash_menu/item_stash_menu.gd`