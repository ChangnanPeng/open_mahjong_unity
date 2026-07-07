# New Rule Implementation Plan

This document turns the new-rule reference into a low-risk implementation sequence.

## Goals

Build a new Python backend rule variant with:

- Blood-battle hand flow: a win does not end the hand until three players have won or the wall is exhausted.
- Guobiao/Qingque-like tile set and action style.
- No flowers.
- No dead wall; draw until the live wall is empty.
- Honors included.
- No dingque.
- No immediate kong scoring.
- No chajiao.
- No minimum win limit.
- 0-point wins are legal: a completed hand may win and exit the hand even when it matches no scoring fan.
- No false-win handling.
- Fixed dealer rotation each hand.
- Hidden mid-hand win details; reveal hand/fans/score only at final settlement.
- Concealed-kong tile hidden from other players until final settlement.
- Same-tile discard-win lockout.

Primary references:

- `other/new_rule_reference.md`
- `other/new_rule_live_integration_boundary.md`
- `other/new_rule_discard_win_lockout.md`
- `other/new_rule_multi_ron_implementation.md`
- `other/new_rule_fan_scoring/new_rule_fan_scoring.md`
- `other/new_rule_fan_scoring/new_rule_fan_details.md`

## Source Code Anchors

Existing modules to study or reuse:

- `open_mahjong_server/server/gamestate/game_sichuan/SichuanGameState.py`
  - Best flow skeleton for blood-battle continuation.
- `open_mahjong_server/server/gamestate/game_sichuan/wait_action.py`
  - Blood-battle action resolution and win continuation behavior.
- `open_mahjong_server/server/gamestate/game_sichuan/action_check.py`
  - Sichuan action checks; useful for flow, but do not reuse shunhe/dingque/chajiao rules.
- `open_mahjong_server/server/gamestate/game_guobiao/action_check.py`
  - Better model for chi/peng/kong availability, honors, and no dingque.
- `open_mahjong_server/server/gamestate/game_guobiao/init_tiles.py`
  - Useful tile-wall reference.
- `open_mahjong_server/server/gamestate/game_mmcr/init_tiles.py`
  - Qingque no-flower wall reference.
- `open_mahjong_server/server/game_calculation/guobiao_hepai_check.py`
  - Existing Python fan calculator reference, but new rule should be cleaner and smaller.
- `open_mahjong_server/server/game_calculation/game_calculation_service.py`
  - Service integration point after the new calculator exists.

## Phase 1: Make Original Backend Testable

Before code changes:

1. Install or expose Python 3.12.
2. Create `.venv` under `open_mahjong_server`.
3. Install `requirements.txt`.
4. Run import probes from `other/new_rule_local_test_plan.md`.
5. Run a direct Guobiao/Sichuan calculation probe.

Exit condition:

- Existing calculation modules can be imported and called.
- Any environment caveats are recorded.

Current status:

- Done. Python 3.12.10 was installed with `winget`.
- Backend virtual environment was created at `open_mahjong_server/.venv`.
- Dependencies from `requirements.txt` were installed successfully.
- Core dependency imports, `GameCalculationService`, `SichuanGameState`, and Guobiao action-check imports succeeded.
- Guobiao direct calculation probe succeeded.
- Sichuan direct calculation is callable, but the first ad-hoc sample should remain a smoke test only.

## Phase 2: Build New Scoring Module First

Add a new isolated scoring package before touching game flow:

```text
open_mahjong_server/server/game_calculation/new_rule/
```

Suggested files:

```text
__init__.py
tiles.py
decompose.py
fan_definitions.py
fan_detector.py
scoring.py
test_new_rule_scoring.py
```

Responsibilities:

- `tiles.py`: tile constants, suit/honor helpers, normalization.
- `decompose.py`: standard hand decomposition plus special hand recognition helpers.
- `fan_definitions.py`: stable fan IDs, Chinese names, point values, row IDs.
- `fan_detector.py`: detect fan candidates from a resolved hand context.
- `scoring.py`: apply row maximums, documented repeat exceptions, and 20-point cap.
- `test_new_rule_scoring.py`: plain Python assertion tests at first.

Do not wire into live game state yet.

Exit condition:

- All 50 fan entries have at least one test or deliberate coverage note.
- Special edge cases from `new_rule_fan_details.md` are covered.

Current status:

- Started. Created isolated package at `open_mahjong_server/server/game_calculation/new_rule/`.
- Added tile helpers, standard/special decomposition helpers, fan definitions, fan detector, scoring entry point, and direct smoke tests.
- Current test command:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_scoring.py
```

- Current smoke tests pass: 34 tests.
- Current coverage includes representative cases for every fan row, plus direct checks for lower-level patterns that would otherwise only be covered through higher-row upgrades: lower wind patterns, individual dragon triplets, all simples, closed hand, all triplets, and two concealed triplets.
- Ambiguous decomposition coverage now checks that special shapes and standard decompositions are evaluated as separate candidates. In particular, a hand that can be read as both seven pairs and standard sequences must not combine `seven_pairs` with sequence-only fans from the standard candidate.
- Row-rule coverage now checks that repeatable low-level exceptions such as `two_suit_triplets` are suppressed when a higher pattern from the same row applies.
- Tests mainly assert stable English fan IDs. Chinese names are still available in `ScoreResult.fan_names`, but English IDs make console encoding issues less disruptive.
- The scoring implementation is wired into `GameCalculationService` through the new-rule service methods.

## Phase 3: Add Service-Level Entry Point

Add a method to `GameCalculationService`, for example:

```text
NewRule_hepai_check(...)
NewRule_tingpai_check(...)
```

Keep the signature close to existing methods where possible:

- `hand_list`
- `tiles_combination`
- `way_to_hepai`
- `get_tile`
- optional context for timing-sensitive fans and pre-win shape

Important: nine-gates and several timing fans need context beyond final 14 tiles. The new API should allow a context object rather than forcing all detection from the final hand.

Exit condition:

- Direct service-level calls work without importing the full FastAPI server.

Current status:

- Started. Added thin service methods:
  - `GameCalculationService.NewRule_hepai_check(...)`
  - `GameCalculationService.NewRule_hepai_detail(...)`
  - `GameCalculationService.NewRule_tingpai_check(...)`
- `NewRule_hepai_check` returns `(points, fan_names)` to match the style of existing calculation-service methods.
- `NewRule_hepai_detail` returns points, raw points, stable English fan IDs, and Chinese fan names for tests and future game-flow integration.
- `NewRule_tingpai_check` uses the new scoring engine as source of truth: it brute-force tests all 34 tile ids, respects the four-copy limit across concealed tiles and declared melds, and returns winning candidate tile ids.
- Added service smoke test:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_service.py
```

- Current service smoke tests pass: 5 tests, including a public-service check for repeatable row-rule suppression.

Additional tingpai smoke test:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_tingpai.py
```

- Current tingpai smoke tests pass: 5 tests.

## Phase 4: Create New Game State Skeleton

Suggested path:

```text
open_mahjong_server/server/gamestate/game_new_rule/
```

Start from the Sichuan structure, but remove or replace:

- dingque phase
- chajiao
- immediate kong scoring
- Sichuan shunhe
- Sichuan dealer repeat logic
- Sichuan tile wall of 108 tiles

Borrow from Guobiao/Qingque:

- honors enabled
- chi/peng/kong action model
- final discard handling style
- concealed-kong hidden information model
- fixed dealer rotation

Exit condition:

- A scripted game-flow probe can instantiate the state and drive a few deterministic steps without the full client.

Current status:

- Started. Created isolated skeleton package at `open_mahjong_server/server/gamestate/game_new_rule/`.
- Added:
  - `NewRuleGameState`
  - `NewRulePlayer`
  - 136-tile no-flower wall initialization
  - dealer 14-tile / non-dealer 13-tile opening deal
  - fixed dealer rotation helper
  - blood-battle hand-end helper: end at 3 winners or exhausted wall
  - next-active-player helper that skips exited winners
  - same-tile discard-win lockout helper methods
- This skeleton is now wired into hidden backend manager/router/room-creation shells, but not into normal client UI or persistence.
- Current skeleton test command:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_gamestate.py
```

- Current skeleton tests pass: 53 tests.

## Phase 5: Implement New Flow Rules

Order of implementation:

1. 136-tile no-flower wall.
2. Fixed dealer rotation.
3. Blood-battle win continuation.
4. Deferred final settlement and hidden mid-hand win payload.
5. Independent multi-ron choices.
6. Same-tile discard-win lockout.
7. Post-claim action restrictions.
8. Final-discard response restriction.
9. Concealed-kong visibility.

Exit condition:

- Flow probes cover the critical cases listed in `new_rule_local_test_plan.md`.

Current status:

- Started the first action-check layer in `open_mahjong_server/server/gamestate/game_new_rule/action_check.py`.
- Added pure-Python action checks for:
  - own draw: `hu_self`, `angang`, `jiagang`, `cut`
  - discard response: `chi_left`, `chi_mid`, `chi_right`, `peng`, `gang`, `hu`
  - final discard after wall exhaustion: `hu` only, no chi/peng/gang
  - added-kong robbery: `hu` only for eligible non-winning opponents
  - after chi/peng: only `cut`
  - same-tile discard-win lockout blocking discard win and robbing-kong win
- This layer currently uses each player's `waiting_tiles` cache as the hu eligibility source.
- Added `refresh_waiting_tiles(game_state, player_index)` to populate that cache through `GameCalculationService.NewRule_tingpai_check` when available, or directly through the isolated new-rule tingpai checker otherwise.
- Action checks still consume `waiting_tiles` as an explicit cache. The live state-machine integration should call `refresh_waiting_tiles` after hand-changing transitions such as draw, discard, chi, peng, kong declaration, and supplement draw.
- Added minimal scriptable flow methods on `NewRuleGameState`:
  - `record_discard(...)`
  - `record_discard_win_pass(...)`
  - `record_discard_win(...)`
  - `draw_after_discard_resolution(...)`
  - `resolve_discard_win_responses(...)`
  - `resolve_discard_claim_responses(...)`
  - `record_self_draw_win(...)`
  - `declare_concealed_kong(...)`
  - `attempt_added_kong(...)`
  - `resolve_added_kong_responses(...)`
  - `begin_hand_action(...)`
  - `begin_only_cut(...)`
  - `apply_turn_action(...)`
  - `continue_after_discard_responses(...)`
  - `continue_after_rob_kong_responses(...)`
- Current flow probes cover:
  - a skipped discard win creating same-tile lockout
  - the player's next discard clearing the old lockout while immediately starting the new discarded-tile lockout
  - discard-win settlement being stored for deferred final reveal
  - blood-battle continuation drawing from the next active player after the final accepted discard winner
  - wall exhaustion ending the hand
  - independent multi-ron choices on the same discard
  - a mixed `hu`/`pass` discard response locking only the passing non-winner
  - ending immediately when the third winner is produced by discard win
  - rejecting a locked-out discard win
  - choosing one chi/peng/gang claim after discard wins are declined
  - peng/gang priority over chi; same priority resolved by nearest active player after the discarder
  - chi only by the fixed next seat after the discarder, not by the next active player
  - chi/peng forcing the claimant into discard-only status
  - discard kong drawing a live-wall supplement tile and entering normal hand-action status
  - self-draw win settlement being deferred
  - calculated discard-win score changes: discarder pays `6X`
  - calculated multi-ron score changes: each accepted winner charges the same discarder independently
  - calculated self-draw score changes based on remaining non-winning players
  - concealed kong storing the true `G{tile}` server-side while returning public `G0`
  - concealed kong drawing a live-wall supplement tile
  - added kong opening a robbing-kong response window before mutating hand/meld state
  - unrobbed added kong upgrading `k{tile}` to `g{tile}` and drawing a live-wall supplement tile
  - robbed added kong deferring rob-kong settlement, not upgrading the meld, and not drawing a supplement tile
  - robbing kong respecting same-tile discard-win lockout
  - hand-action windows refreshing waiting tiles from the pre-draw hand before self-draw checks
  - selected discards refreshing other players' waiting caches and opening discard-response windows
  - self-draw wins continuing to the next active player's draw when the hand does not end
  - concealed kong selections returning a follow-up hand-action window after supplement draw
  - added kong selections opening a robbing-kong response window without mutating the triplet yet
  - discard response windows returning consistent next-window payloads after multi-ron, claim, or no-claim outcomes
  - discard claim responses being skipped when any discard winner accepts `hu`
  - the final discard ending the hand by exhausted wall when nobody wins it
  - robbing-kong response windows returning consistent next-window payloads after robbed or unrobbed outcomes
  - no-win discard response resolution stopping before draw so lower-priority chi/peng/gang claims can still resolve
  - a longer scripted flow using only public driver helpers:
    draw action -> discard -> peng claim -> forced discard -> pass plus discard win -> next active draw
- `resolve_discard_win_responses(...)` intentionally handles only `hu`, `pass`, and no-op responses.
- `resolve_discard_claim_responses(...)` is that separate layer. It ignores discard-win handling by design and should be called only after discard wins are declined or unavailable.
- Current action-check test command:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_action_check.py
```

- Current action-check tests pass: 9 tests.
- Current gamestate skeleton tests pass: 53 tests.

## Phase 6: Register Rule Variant

Only after isolated tests pass:

- Add new room creation path if needed.
- Add `GameStateManager` mapping for the new game state.
- Add client-facing rule identifier.
- Add minimal response/broadcast compatibility changes.

This is where Unity or web-client work may become relevant, but it should not be required for scoring development.

Current status:

- Planning boundary documented in `other/new_rule_live_integration_boundary.md`.
- Added live-integration shell fields and methods to `NewRuleGameState`:
  - `game_task`
  - `server_action_tick`
  - `action_events`
  - `action_queues`
  - `waiting_players_list`
  - `action_dict`
  - `action_priority`
  - `submit_action(...)`
  - `wait_action(...)`
  - `cleanup_game_state(...)`
  - `player_disconnect(...)`
  - `player_reconnect(...)`
- Added `open_mahjong_server/server/gamestate/game_new_rule/get_action.py` as a thin action-submission adapter for future WebSocket routing.
- Added the first live-loop orchestration skeleton on `NewRuleGameState`:
  - `open_action_window(...)`
  - `resolve_action_window(...)`
  - `apply_action_results(...)`
  - This maps queued live actions back into the already tested driver helpers for hand actions, discard responses, and robbing-kong responses.
- Added minimal hidden-information-safe payload builders in `open_mahjong_server/server/gamestate/game_new_rule/boardcast.py`:
  - player/game views
  - ask-action payloads
  - visible action payloads
  - final settlement payloads
  - final settlement applying deferred score changes exactly once
  - final settlement summing multiple deferred score changes exactly once
  - concealed kong masking as `G0` for other players before final reveal
  - mid-hand win fan/score hiding until final reveal
- Added adapter tests:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_get_action.py
```

- Current get-action adapter tests pass: 4 tests.
- Added a cancellable draft `run_game_loop(...)` that:
  - initializes a round
  - opens the first hand-action window
  - resolves queued actions through the orchestration skeleton
  - records hidden-information-safe ask/final payloads in `outbound_payloads`
  - flushes payloads to connected players through `game_server.user_id_to_connection` when available
- Added WebSocket send/reconnect shell support:
  - `send_payload_to_player(...)`
  - `flush_outbound_payloads(...)`
  - `build_reconnect_payload(...)`
  - `player_reconnect(...)` now sends a hidden-information-safe reconnect snapshot when a connection exists.
  - Missing connections keep payloads in the local outbox.
- Current boardcast payload tests pass: 10 tests.
- Added backend router support for:
  - `gamestate/new_rule/cut_tile`
  - `gamestate/new_rule/send_action`
- Current router tests pass: 3 tests.
- Added `GameStateManager` support for hidden `room_rule = "new_rule"` room data:
  - imports `NewRuleGameState`
  - maps `room_id_to_NewRuleGameState`
  - starts the draft loop
  - maps users and gamestate ids
  - supports room-id lookup
  - cleans up new-rule maps
- Current gamestate-manager tests pass: 1 test.
- Added hidden backend room creation support for `room_rule = "new_rule"`:
  - `RoomManager.create_NewRule_room(...)`
  - `GameServer.create_NewRule_room(...)`
  - `room/create_NewRule_room` router handler
  - `NewRuleRoomValidator` for generic room fields
- The hidden room route fixes `hepai_limit = 0` and `open_cuohe = False`.
- The hidden room route currently forces `allow_spectator = False` because spectator/realtime spectator reconnect support has not been implemented yet.
- The hidden room route sets `hidden_room = True`; public `get_room_list()` filters hidden rooms, generic `join_room()` rejects them, hidden-room bot changes require the host, and generic ready/kick paths still require valid room membership/host authority, while the host can still recover the room through `sync_my_room`.
- Running `NewRuleGameState` instances also set `spectator_enabled = False`, so `GameStateManager.get_spectator_list()` does not expose new-rule games while spectator support is pending.
- New-rule scoring returns `is_win` separately from `points`, so 0-point legal hands are not confused with invalid hands.
- Confirmed wins now build deferred settlement details through the new-rule calculator when no explicit test settlement is provided:
  - `is_win`
  - `points`
  - `raw_points`
  - `fan_ids`
  - `fan_names`
  - `score_changes`
  - This includes 0-point legal wins with empty fan lists.
- This route is for backend-only testing and is still intentionally not exposed in normal Unity/client room-creation UI.
- Current room-creation smoke test:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_room_creation.py
```

- Full current new-rule backend smoke suite:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe run_new_rule_tests.py
```

- Current room-creation/start-game/message-path smoke tests pass: 38 tests.
- The hidden backend smoke now covers:
  - new-rule room creation with spectator support forced off, including when a caller explicitly requests `allow_spectator = True`
  - hidden new-rule rooms are filtered from public room lists, reject generic join-by-room-id, but remain syncable by the room host
  - hidden new-rule bot changes reject non-host callers while still allowing the host to add bots for backend testing
  - hidden new-rule start-game follows the existing host-only rule: non-host callers are rejected without creating a game state, while the host can still start the backend test game
  - hidden new-rule ready/kick handling still uses the generic membership/host checks, so non-member ready requests and non-host kick requests fail without mutating room state
  - `GameServer.create_NewRule_room(...)` wrapper forwarding into the hidden room-manager path without enabling spectators
  - a fake-WebSocket `GameServer.connect(...)` session smoke:
    connect -> store session -> `room/create_NewRule_room` -> `room/start_game` -> `gamestate/new_rule/cut_tile`
  - a four-session fake-WebSocket `GameServer.connect(...)` smoke:
    four connected sessions -> hidden room setup -> `room/start_game` -> current-player `gamestate/new_rule/ask_action` reaches the mapped websocket -> current player cuts through the router
  - manager-level spectator listing skips running new-rule games because `spectator_enabled = False`
  - protocol-level in-process dispatch of `room/create_NewRule_room` -> `room/start_game` -> `gamestate/new_rule/cut_tile`
  - hidden-room start-game emits the first `gamestate/new_rule/ask_action` payload to the connected current player's websocket
  - first `gamestate/new_rule/cut_tile`
  - discard-response `gamestate/new_rule/send_action` with `hu`
  - discard-response `gamestate/new_rule/send_action` with `pass`
  - discard-claim `gamestate/new_rule/send_action` with `chi_right`, `peng`, and `gang`
  - claim resolution into forced discard-only state for chi/peng
  - discard-kong supplement draw into normal hand-action state
  - hand-action `gamestate/new_rule/send_action` with `angang`
  - hand-action `gamestate/new_rule/send_action` with `jiagang`, followed by robbing-kong `pass`
  - robbing-kong `gamestate/new_rule/send_action` with `hu`
  - `END` window emission of four final-settlement reveal payloads
  - 0-point legal discard win eligibility through the live message path
  - live-message deferred settlement details for 0-point wins, self-draw wins, discard wins, and robbing-kong wins
  - live-message final-settlement player scores after deferred `score_changes` are applied
  - connected manager-level reconnect flow:
    player disconnect -> player reconnect -> sanitized `gamestate/new_rule/reconnect` payload is sent to that player's websocket with own hand visible, other hands hidden, concealed kong masked as `G0`, pending actions, and action tick
  - connected manager-level reconnect-after-END flow:
    ended hand -> player reconnect -> `gamestate/new_rule/reconnect` payload reveals final hands, concealed kong true tiles, deferred settlements, ended_by, and final scores without double-applying score changes
  - connected multi-ron message flow:
    start hidden room -> host discard -> two players accept `hu` on the same discard -> two independent settlements -> next active player after the final accepted winner draws
  - connected multi-ron hand-end message flow:
    one existing winner -> host discard -> two players accept `hu` on the same discard as second and third winners -> `END` -> final settlement payloads with both discard-win score changes applied
  - connected late-action-after-END flow:
    hand ends by multi-ron -> stale `send_action` after `END` is ignored -> settlement records, scores, action tick, and payload count do not mutate
  - connected stale-action-after-window-change flow:
    discard win advances the game into the next player's hand-action window -> stale response from the previous discard-response tick is ignored -> hand, lockout state, settlements, action tick, and payload count do not mutate
  - connected mixed `hu`/`pass` discard-response flow:
    start hidden room -> host discard -> one player accepts `hu` and another eligible player passes in the same response window -> only the passing non-winner records same-tile lockout -> next active player after the final accepted winner draws
  - connected mixed hu-vs-claim response flow:
    start hidden room -> host discard -> one player submits `peng` and another accepts `hu` in the same response window -> hu settlement wins -> peng is skipped -> next active player after the final accepted winner draws
  - a connected four-player scripted message flow:
    start hidden room -> host discard -> third-seat `peng` -> forced discard -> fourth-seat discard win -> blood-battle continuation draw
  - a connected four-player self-draw message flow:
    start hidden room -> current-player `hu_self` -> winner exits -> next active player draws and continues
  - a connected four-player hand-end message flow:
    two existing winners -> current-player `hu_self` as third winner -> `END` -> final settlement payloads
  - a connected four-player concealed-kong message flow:
    start hidden room -> `angang` -> supplement draw -> current player discards -> next active player draws
  - a connected four-player unrobbed added-kong message flow:
    start hidden room -> `jiagang` -> robbing-kong `pass` -> added kong finalizes -> supplement draw -> current player discards -> response `pass` -> next active player draws
  - a connected four-player robbed added-kong message flow:
    start hidden room -> `jiagang` -> robbing-kong `hu` -> added kong remains unfinalized -> robbing winner exits -> next active player draws
  - a connected four-player final-discard wall-exhaustion message flow:
    start hidden room -> empty wall -> current player discards final tile -> no discard winners -> `END` -> final settlement payloads with `ended_by = wall`

## Phase 7: Full Integration Testing

Run in this order:

1. Scoring tests.
2. Service-level calculation probes.
3. Game-state flow probes.
4. Protocol-level in-process message dispatch smoke.
5. Fake-WebSocket `GameServer.connect(...)` smoke without FastAPI/database.
6. FastAPI server smoke test.
7. WebSocket/local bot game if feasible.
8. Unity/web client only after backend behavior is stable.

## Current Development Loop

Use this loop for normal new-rule work:

1. Rule/fan scoring changes:
   - update `other/new_rule_fan_scoring/new_rule_fan_details.md` first if semantics change
   - edit `server/game_calculation/new_rule/`
   - run `.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_scoring.py`
   - run `.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_service.py`
   - run `.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_tingpai.py` if waiting/win eligibility changed
2. Game-flow changes:
   - update `other/new_rule_reference.md` or the focused rule-flow note first if behavior changes
   - edit `server/gamestate/game_new_rule/`
   - run the focused gamestate/action test that matches the change
3. Router/room/live-path changes:
   - run `.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_router.py`
   - run `.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_room_creation.py`
4. Before treating a change as locally safe:
   - run `.\.venv\Scripts\python.exe run_new_rule_tests.py` from `open_mahjong_server`

## Risk Notes

- The full server imports database and chat-server components early, so pure rules work should avoid full `server.server` import at first.
- Existing source comments display as mojibake in the current terminal, so rely on code structure and known behavior rather than terminal-rendered Chinese comments.
- The new scoring API must carry context, especially for:
  - pre-win nine-gates waiting shape
  - self-draw vs discard win
  - robbing kong
  - kong supplement draw
  - final wall tile/final discard
  - exposed vs concealed meld state
  - finalized vs robbed kongs

## Immediate Next Step

Continue rule development with the Python-only loop above. The in-process protocol smoke already exercises the same room/gamestate router functions that `server.py` would call after login, while avoiding the database and chat-server dependencies pulled in by full FastAPI startup.

Move to full FastAPI/WebSocket smoke only when the goal includes real login, database setup, or client integration.
