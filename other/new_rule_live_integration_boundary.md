# New Rule Live Integration Boundary

This document lists the server/client integration work needed before the new
rule can become a selectable live backend rule. The current new-rule code is
still an isolated, script-testable rules skeleton.

## Current Local Status

Implemented and tested in isolation:

- New-rule scoring package under `open_mahjong_server/server/game_calculation/new_rule/`.
- Service entries:
  - `GameCalculationService.NewRule_hepai_check(...)`
  - `GameCalculationService.NewRule_hepai_detail(...)`
  - `GameCalculationService.NewRule_tingpai_check(...)`
- New-rule game-state skeleton under `open_mahjong_server/server/gamestate/game_new_rule/`.
- Scripted flow probes for:
  - wall/deal/dealer rotation
  - blood-battle continuation
  - same-tile discard-win lockout
  - discard win / multi-ron
  - chi/peng/gang claims
  - self-draw, concealed kong, added kong, robbing kong
  - driver-style turn and response windows
- Minimal live-integration shell fields/methods on `NewRuleGameState`:
  - action queue/event containers
  - `submit_action(...)`
  - `wait_action(...)`
  - `cleanup_game_state(...)`
  - `player_disconnect(...)`
  - `player_reconnect(...)`
- Thin action-submission adapter:
  - `open_mahjong_server/server/gamestate/game_new_rule/get_action.py`
  - supports player-connection lookup, AI direct submission, cut/kong payload validation, and stale response tick rejection
- First action-resolution orchestration skeleton:
  - `open_action_window(...)`
  - `resolve_action_window(...)`
  - `apply_action_results(...)`
  - maps queued live actions into the existing tested driver helpers for hand actions, discard responses, and robbing-kong responses
- Minimal hidden-information-safe payload builders:
  - `open_mahjong_server/server/gamestate/game_new_rule/boardcast.py`
  - player/game views
  - ask-action payloads
  - visible action payloads
  - final settlement payloads
  - final settlement applies deferred score changes exactly once before revealing player scores
  - final settlement sums multiple deferred score changes exactly once
  - concealed kong masking before final reveal
  - mid-hand win scoring/fan hiding before final reveal
- WebSocket send/reconnect shell:
  - `send_payload_to_player(...)`
  - `flush_outbound_payloads(...)`
  - `reconnect_payload(...)`
  - connected players receive payloads through `websocket.send_json(...)`
  - disconnected players retain payloads in the local outbox
- Router support:
  - `gamestate/new_rule/cut_tile`
  - `gamestate/new_rule/send_action`
- `GameStateManager` support for hidden `room_rule = "new_rule"` room data:
  - import and room-id map
  - start-game branch
  - user/gamestate maps
  - room lookup
  - cleanup map removal
- Hidden backend room-creation path:
  - `RoomManager.create_NewRule_room(...)`
  - `GameServer.create_NewRule_room(...)`
  - `room/create_NewRule_room`
  - generic `NewRuleRoomValidator`
  - `hidden_room = True`, so normal room-list queries skip backend-only new-rule test rooms, generic `join_room()` rejects them, bot changes require the host, and generic ready/kick paths remain protected by membership/host checks
  - `allow_spectator = False` is forced through both the room-manager path and the `GameServer.create_NewRule_room(...)` wrapper
  - `NewRuleGameState.spectator_enabled = False`, so manager-level spectator listing also skips new-rule games while spectator support is pending
  - fixed `hepai_limit = 0` and `open_cuohe = False`
  - confirmed wins build deferred final-settlement details through the new-rule calculator when the live path does not provide an explicit test settlement:
    `is_win`, `points`, `raw_points`, `fan_ids`, `fan_names`, and `score_changes`
  - smoke-tested through protocol-level in-process dispatch:
    `room/create_NewRule_room` -> `room/start_game` -> `gamestate/new_rule/cut_tile`
  - smoke-tested through `GameStateManager.start_game(...)` into a draft `NewRuleGameState`
  - smoke-tested through the first `gamestate/new_rule/cut_tile` message into the draft loop
  - smoke-tested through discard-response `gamestate/new_rule/send_action` messages for `hu` and `pass`
  - smoke-tested through discard-claim `gamestate/new_rule/send_action` messages for `chi_right`, `peng`, and `gang`
  - smoke-tested through hand-action `gamestate/new_rule/send_action` messages for `angang` and unrobbed `jiagang`
  - smoke-tested through robbing-kong `gamestate/new_rule/send_action` message for `hu`
  - smoke-tested through `END` window final-settlement payload reveal
  - smoke-tested through live-message deferred settlement details, including 0-point wins with empty fan lists
  - smoke-tested through score-change formulas for discard wins and self-draw wins
  - smoke-tested through calculated multi-ron score changes where each accepted winner charges the discarder independently
  - smoke-tested through connected final-settlement payloads that reveal player scores after deferred score changes are applied
  - smoke-tested through connected manager-level reconnect flow:
    disconnect -> reconnect -> sanitized `gamestate/new_rule/reconnect` payload reaches the player's websocket with own hand visible, other hands hidden, concealed kong masked as `G0`, pending actions, and action tick
  - smoke-tested through connected manager-level reconnect-after-END flow:
    ended hand -> reconnect -> `gamestate/new_rule/reconnect` reveals final hands, concealed kong true tiles, deferred settlements, ended_by, and final scores without double-applying score changes
  - smoke-tested through connected multi-ron message flow:
    discard -> two accepted `hu` responses -> two independent settlements -> next active player after the final accepted winner draws
  - smoke-tested through connected multi-ron hand-end flow:
    one existing winner -> discard -> two accepted `hu` responses as second and third winners -> `END` -> final settlement payloads with both discard-win score changes applied
  - smoke-tested through connected late-action-after-END flow:
    hand ends by multi-ron -> stale `send_action` after `END` is ignored without mutating settlements, scores, action tick, or payload count
  - smoke-tested through connected stale-action-after-window-change flow:
    discard win advances to the next player's hand-action window -> stale response from the old discard-response tick is ignored without mutating hand, lockout state, settlements, action tick, or payload count
  - smoke-tested through mixed `hu`/`pass` discard response semantics: only passing non-winners enter same-tile lockout
  - smoke-tested through connected mixed `hu`/`pass` response flow:
    discard -> accepted `hu` plus eligible `pass` in the same window -> only the passing non-winner records same-tile lockout -> next active player after the final accepted winner draws
  - smoke-tested that chi/peng/gang claims are skipped when any discard winner accepts `hu`
  - smoke-tested through connected mixed hu-vs-claim response flow:
    discard -> `peng` claim response plus accepted `hu` response -> hu settlement wins -> peng skipped -> next active player after the final accepted winner draws
  - smoke-tested through a connected four-player scripted message flow:
    start hidden room -> discard -> `peng` -> forced discard -> discard win -> blood-battle continuation draw
  - smoke-tested through connected self-draw continuation:
    start hidden room -> `hu_self` -> winner exits -> next active player draws
  - smoke-tested through connected third-winner hand end:
    two existing winners -> `hu_self` -> `END` -> final settlement payloads
  - smoke-tested through connected concealed-kong continuation:
    `angang` -> supplement draw -> discard -> next active player draws
  - smoke-tested through connected unrobbed added-kong continuation:
    `jiagang` -> robbing-kong `pass` -> supplement draw -> discard -> response `pass` -> next active player draws
  - smoke-tested through connected robbed added-kong continuation:
    `jiagang` -> robbing-kong `hu` -> kong remains unfinalized -> robbing winner exits -> next active player draws
  - smoke-tested through connected final-discard wall exhaustion:
    empty wall -> current player discards final tile -> no discard winners -> `END` -> final settlement payloads with `ended_by = wall`

Not implemented yet:

- Full production WebSocket/lifespan smoke with real login, database setup, and client-style sessions.
- Full FastAPI/WebSocket smoke with real login/lifespan.
- Game record persistence.
- Client room-creation UI.
- Unity/client action handling for the new `room_rule`.

## Rule Identifier

Recommended identifiers:

- `room_rule`: `new_rule`
- `sub_rule`: `new_rule/standard`
- WebSocket response prefix: `gamestate/new_rule/...`

The existing action names can mostly be reused:

- Hand action: `cut`, `hu_self`, `angang`, `jiagang`
- Other action: `hu`, `chi_left`, `chi_mid`, `chi_right`, `peng`, `gang`, `pass`
- Broadcast-style action names likely reusable: `deal_tile`, `deal_gang_tile`

Important mismatch to watch:

- Existing Guobiao/Riichi sometimes use `hu_first`, `hu_second`, `hu_third` for relative-position ron.
- Sichuan uses simpler `hu`.
- The new-rule skeleton currently uses `hu` for discard win and robbing kong. Prefer staying with `hu` to match independent multi-ron behavior, unless the client requires relative labels.

## Server Integration Checklist

### 1. `GameStateManager`

File:

- `open_mahjong_server/server/gamestate/gamestate_manager.py`

Status:

- Import `NewRuleGameState`.
- Add `room_id_to_NewRuleGameState`.
- Add a `room_rule == "new_rule"` branch in `start_game`.
- Add cleanup support in `cleanup_game_state_complete`.
- Add lookup support in `get_game_state_by_room_id`.
- Done for hidden/manual room data.

Risk:

- The current `NewRuleGameState` exposes a cancellable draft `run_game_loop` and can flush payloads to connected players through `game_server.user_id_to_connection`, but it has only been exercised through lightweight in-process fakes rather than full FastAPI login/lifespan.
- Spectator methods are still missing. Reconnect payloads exist for players, but spectator/realtime spectator reconnect is not implemented; hidden new-rule room creation currently forces `allow_spectator = False`, and `NewRuleGameState.spectator_enabled = False` keeps it out of manager spectator listings until that support exists.

### 2. Room Creation

Files:

- `open_mahjong_server/server/room/room_manager.py`
- `open_mahjong_server/server/room/room_router.py`
- `open_mahjong_server/server/server.py`

Status:

- Done as a hidden backend-only route for smoke testing.
- `room/create_NewRule_room` builds `room_data` with:
  - `room_rule = "new_rule"`
  - `sub_rule = "new_rule/standard"`
  - `hepai_limit = 0`
  - `open_cuohe = False`
  - `tourist_limit`, `random_seed`, timers
  - `allow_spectator = False`, forced off while spectator support is pending
- It uses `NewRuleRoomValidator` for generic room fields only, not rule semantics.
- Win eligibility must use the new-rule `is_win` result or waiting-tile cache, not `points > 0`, because 0-point completed hands are legal wins.

Risk:

- Existing validators carry Guobiao assumptions such as configurable starting fan and false-win flags. The new rule should avoid exposing those options.
- This route is intentionally not wired into normal client room-creation UI yet.

### 3. Game-State Message Routing

File:

- `open_mahjong_server/server/gamestate/gamestate_router.py`

Needed changes:

- Accept `gamestate/new_rule/cut_tile`.
- Accept `gamestate/new_rule/send_action`.
- Reuse the existing `handle_cut_tile` and `handle_send_action` mechanics if the new state uses the same `get_action` adapter shape.

Risk:

- Current routing names are mixed: Guobiao uses `gamestate/GB/...`, Riichi uses `gamestate/riichi/...`.
- A new explicit prefix `gamestate/new_rule/...` is clearer, but the client must know it.

### 4. Action Submission Adapter

Existing shared path:

- `open_mahjong_server/server/gamestate/public/ai/get_action.py`
- Rule-specific `get_action.py` files in existing rule folders

Needed changes:

- Add `game_new_rule/get_action.py` or make the public adapter dispatch to a new-rule handler.
- Validate:
  - current player for hand actions
  - eligible waiting players for discard/rob-kong responses
  - `target_tile` for `angang` and `jiagang`
  - `TileId` / `cutIndex` for discard
- Convert client messages into calls to:
  - `begin_hand_action`
  - `apply_turn_action`
  - `continue_after_discard_responses`
  - `continue_after_rob_kong_responses`

Risk:

- Existing `wait_action` logic usually resolves one winner/claim by priority. New rule needs independent multi-ron decisions, and pass must not automatically imply every eligible winner wins.

### 5. Live Async Game Loop

Recommended source skeletons:

- Flow continuation: `open_mahjong_server/server/gamestate/game_sichuan/SichuanGameState.py`
- General action/broadcast loop: `open_mahjong_server/server/gamestate/game_guobiao/GuobiaoGameState.py`

Needed methods on `NewRuleGameState`:

- `run_game_loop`
- `wait_action`
- `cleanup_game_state`
- `player_disconnect`
- `player_reconnect`
- spectator support before `allow_spectator` can be enabled

Recommended loop states:

- `waiting_hand_action`
- `waiting_only_cut`
- `waiting_discard_response`
- `waiting_rob_kong`
- `END`

Mapping to existing client-facing statuses:

- Existing clients already understand `waiting_hand_action`.
- Existing spectators/friend manager check `waiting_action_after_cut` and `waiting_action_qianggang`. Either:
  - use existing names in the live loop, or
  - update reconnect/spectator code to also recognize the new names.

Risk:

- The isolated skeleton uses `waiting_discard_response` and `waiting_rob_kong`; existing broadcasting code expects `waiting_action_after_cut` and `waiting_action_qianggang`.

### 6. Broadcasts And Reconnect

Likely reusable modules:

- `open_mahjong_server/server/gamestate/game_guobiao/boardcast.py`
- `open_mahjong_server/server/gamestate/game_sichuan/boardcast.py`
- `open_mahjong_server/server/friend/friend_manager.py`
- `open_mahjong_server/server/response.py`

Needed broadcast behavior:

- `game_start`: include `room_rule = "new_rule"` and `sub_rule = "new_rule/standard"`.
- `broadcast_hand_action`: ask current player for `cut`, `hu_self`, `angang`, `jiagang`.
- `ask_other_action`: ask each eligible responder for `hu`, `pass`, claim actions.
- `do_action`: broadcast visible actions.
- Concealed kong:
  - owner sees true `G{tile}`.
  - other players/spectators see `G0` or masked ids.
- Mid-hand win:
  - hide hand, fan list, score, score changes, and non-public self-draw tile until final settlement.
- End settlement:
  - reveal final hands, fan names/ids, scores, score changes, and concealed-kong true tiles.

Risk:

- Existing `Do_action_info` includes fields that can reveal kong/hu details early if reused naively.
- Existing reconnect payloads may expose full player state; new-rule reconnect must preserve the same hidden-information rules.

### 7. Game Records And Database

Existing rule-specific examples:

- `open_mahjong_server/server/database/sichuan/store_sichuan.py`
- `open_mahjong_server/server/database/qingque/store_qingque.py`
- `open_mahjong_server/server/database/classical/store_classical.py`

Needed changes:

- Decide whether the first live test writes records at all.
- If yes, add `database/new_rule/store_new_rule.py`.
- Ensure `game_title` includes:
  - `rule = "new_rule"`
  - `sub_rule = "new_rule/standard"`
  - `room_type`
- Add fan-stat mapping for the new 50 fan ids later, after scoring behavior is stable.

Risk:

- New fan ids are currently English-stable in code and Chinese names in output. Database fan stat tables likely expect existing Chinese-name mappings.

### 8. Client / Unity Touch Points

Likely needed:

- Room creation UI entry for `new_rule`.
- WebSocket send type for `room/create_NewRule_room`.
- Game-state route prefix `gamestate/new_rule/...`.
- Action buttons can probably reuse existing action names.
- Display:
  - no flowers
  - no dingque
  - no dead wall
  - no immediate kong score popups
  - hidden mid-hand win detail
  - concealed-kong masks
  - final settlement reveal

Risk:

- If the client assumes Guobiao relative ron names (`hu_first` / `hu_second` / `hu_third`), new-rule `hu` buttons may need mapping.
- If the client assumes every `do_action` hu includes fan/score detail, mid-hand hidden wins need a new or sanitized payload.

## Recommended Integration Order

1. Keep the isolated tests as the safety net.
2. Add live-loop-compatible method names and statuses to `NewRuleGameState`. Done for the shell layer and cancellable draft loop with lightweight player WebSocket flushing; full FastAPI/WebSocket smoke still pending.
3. Implement `game_new_rule/get_action.py` and live action orchestration using the existing driver helpers. Adapter and first orchestration skeleton done.
4. Implement minimal broadcasts by reusing Guobiao payload shapes but sanitizing hidden information. Payload builders, player send/reconnect shell, and new-rule gamestate router paths done.
5. Add `GameStateManager` registration behind `room_rule = "new_rule"`. Done for hidden/manual room data.
6. Add backend room creation route, but keep it hidden from the normal client UI at first. Done.
7. Run a backend-only WebSocket smoke test with bots or scripted clients. Started locally with fake-WebSocket `GameServer.connect(...)` session smokes, including a four-session start/cut path; full FastAPI/WebSocket smoke is still pending.
8. Add Unity/client entry points only after backend live loop is stable.
9. Add persistence/statistics after end-to-end gameplay is stable.

## Minimal Live Smoke Test Target

Before touching Unity, target this backend-only flow:

1. Create a `new_rule` room with four bots or scripted sessions.
2. Start game.
3. Receive `gamestate/new_rule/game_start`.
4. Current player discards.
5. Another player passes or claims.
6. A discard win is accepted by exactly one selected eligible player.
7. Hand continues and next active player draws.
8. Force wall exhaustion or three winners.
9. Receive final settlement with delayed fan/score reveal.
