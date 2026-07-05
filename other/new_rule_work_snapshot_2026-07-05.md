# New Rule Work Snapshot - 2026-07-05

Purpose: preserve the current working context so future work can resume quickly after context compression, restart, or a break.

This is a documentation snapshot, not a git commit. The working tree is currently dirty and contains many untracked new-rule files and Unity/project changes.

## One-Line State

The new rule has a substantial Python backend implementation and a first playable Unity bridge, but the next major step should be protocol alignment: make `game_new_rule` use old-style status names/action fields close to Qingque/Guobiao/Sichuan before continuing bot and Unity parity work.

## Current Repository And Environment

- Repo root: `C:\Users\changnan\Documents\open_mahjong_unity`
- Backend root: `C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server`
- Unity root: `C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_unity`
- Unity editor used locally: `6000.5.2f1`
- Unity Personal license is active.
- Local backend WebSocket:
  - game: `ws://localhost:8081/game`
  - chat: `ws://localhost:8083/chat`
- Local PostgreSQL database: `open_mahjong`
- Local PostgreSQL user/password in `server/test_config.py`: `postgres` / `qwe123`

PowerShell note:

- Be careful with quoting in PowerShell. Complex inline scripts should use a here-string or avoid inline scripts where possible. Quote escaping caused repeated friction earlier.

## Core New-Rule Design

Rules agreed so far:

- 136-tile wall, honors included, no flowers.
- No dead wall / no 14 reserved tiles.
- No dingque.
- No chajiao.
- No immediate kong scoring.
- No cuohe/false-win flow.
- 0-point legal wins are allowed: a complete 4-melds-and-1-pair hand may win even with no scored fan.
- Blood-battle flow:
  - one player winning does not end the hand.
  - winning player exits the hand.
  - hand ends when 3 players have won or the wall is exhausted.
- Fixed dealer rotation each hand.
- Chi only by physical next seat, not next active player.
  - Example: seats A/B/C/D. If B already won/exited, A's discard cannot be chi by C.
- After chi/peng, player must discard before concealed/added kong.
- Same-tile discard-win lockout:
  - if a player skips a legal ron on tile X, they cannot ron tile X until their next discard.
  - self-draw is unaffected.
  - robbed-kong hu is affected.
  - lockouts may accumulate.
  - when the player discards, previous lockouts clear, and the discarded tile becomes the new lockout tile for future same-tile ron.
- Concealed kong is hidden from other players, following Guobiao/Qingque style.
- Mid-hand hu should not reveal fan list/score details.
- Fan list and score details should be revealed at final settlement.

Reference rule docs:

- `other/new_rule_reference.md`
- `other/new_rule_discard_win_lockout.md`
- `other/new_rule_multi_ron_implementation.md`
- `other/new_rule_fan_scoring/new_rule_fan_scoring.md`
- `other/new_rule_fan_scoring/new_rule_fan_details.md`
- `other/new_rule_implementation_plan.md`
- `other/new_rule_live_integration_boundary.md`
- `other/new_rule_local_test_plan.md`

## Implemented Python Backend Areas

Main new-rule packages:

- `open_mahjong_server/server/game_calculation/new_rule/`
- `open_mahjong_server/server/gamestate/game_new_rule/`

Integrated backend areas touched:

- `open_mahjong_server/server/game_calculation/game_calculation_service.py`
- `open_mahjong_server/server/gamestate/gamestate_manager.py`
- `open_mahjong_server/server/gamestate/gamestate_router.py`
- `open_mahjong_server/server/room/room_manager.py`
- `open_mahjong_server/server/room/room_router.py`
- `open_mahjong_server/server/room/room_validators.py`
- `open_mahjong_server/server/server.py`

Known backend test status from recent work:

- `test_new_rule_gamestate.py`: recently 55 tests passed.
- `test_new_rule_boardcast.py`: recently 13 tests passed after final settlement/remain-tile fixes.
- `test_new_rule_room_creation.py`: recently 38 tests passed after final settlement/remain-tile fixes.
- Earlier component-level tests for scoring/service/tingpai/router/get_action/action_check/gamestate_manager also existed and were used during development.

Useful backend commands:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_boardcast.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_gamestate.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_room_creation.py
.\.venv\Scripts\python.exe main.py
```

## Unity Baseline

Original Qingque Unity baseline passed locally:

- tourist login worked.
- Qingque room creation worked.
- adding 3 bots worked.
- start game worked.
- table rendered.
- discarding worked.
- hu and scoring were tested successfully.

Conclusion:

- Local deployment is healthy.
- New-rule Unity failures should generally be treated as new-rule adapter/protocol issues, not generic environment issues.

## Unity New-Rule Bridge State

Implemented enough for first playable smoke:

- Hidden/dev Unity create option sends `room/create_NewRule_room`.
- Room uses:
  - `room_rule = "new_rule"`
  - `sub_rule = "new_rule/standard"`
  - `hepai_limit = 0`
- Unity routes `gamestate/new_rule/...` messages.
- Unity sends new-rule cut/action messages:
  - `gamestate/new_rule/cut_tile`
  - `gamestate/new_rule/send_action`
- Backend emits Unity-compatible bridge payloads:
  - `unity_game_info`
  - `ask_hand_action_info`
  - `ask_other_action_info`
  - `do_action_info`
  - final settlement with `show_result_info`
- Remaining tile count syncs from `unity_game_info.tile_count`.
- Batchmode Unity compile passed with Unity `6000.5.2f1`.

Important Unity files touched:

- `open_mahjong_unity/Assets/Scripts/Config/ConfigManager.cs`
- `open_mahjong_unity/Assets/Scripts/Network/GameStateNetworkManager.cs`
- `open_mahjong_unity/Assets/Scripts/Network/NetworkManager.cs`
- `open_mahjong_unity/Assets/Scripts/Network/RoomNetworkManager.cs`
- `open_mahjong_unity/Assets/Scripts/Network/Serialize/Response.cs`
- `open_mahjong_unity/Assets/Scripts/Room/CreateRoomPanel/CreatePanel.cs`
- `open_mahjong_unity/Assets/Scripts/GameScene/BoardManager/BoardCanvas_CurrentDisplay.cs`

## Unity Playtest Issues Already Hit

Issue 1: start-game popup said unknown message type.

- Cause: Unity `NetworkManager` did not classify `gamestate/new_rule/...` as game-state messages.
- Status: fixed.

Issue 2: after first discard, Unity showed `chi/cancel`; after cancel, player could not discard.

- Cause: visible `do_action` payloads were per viewer but missing `player_index`, so flush skipped them.
- Status: fixed.

Issue 3: choosing chi did not visibly chi.

- Cause:
  - backend changed state, but visible bridge did not emit Unity-compatible `combination_mask`.
  - live loop looked for `result` while claim windows stored `claim_result`.
- Status: fixed in code; Unity retest showed chi could work.

Issue 4: after hu/bots play to terminal state, no round settlement panel; wall exhaustion also stalled.

- Cause:
  - terminal payload did not include Unity's expected `show_result_info`.
  - remain-tile display relied too much on local decrement and could go stale in bot-only turns.
- Status: fixed in code; still needs Unity verification.

Issue 5: bot actions are instant in new-rule room.

- Cause: new-rule currently uses temporary synchronous fallback bot logic, not original async bot pipeline.
- Status: not fixed. This is part of the next protocol/bot work.

## Current Bot Situation

Unity bot buttons:

- `add_bot` / "moqie Robert" uses original user_id `0`.
- `add_smart_bot` / "paixiao Robert" uses original user_id `2`.

But in the new-rule runtime:

- The current bot behavior is temporary fallback logic in `NewRuleGameState._default_bot_action`.
- It passes if pass is legal.
- Otherwise it discards the first hand tile.
- It runs synchronously, so bots appear to act instantly.
- It does not use original `public.ai.auto_cut_ai` or `public.ai.smart_bot_ai`.

Original bot architecture:

- Shared bot files:
  - `open_mahjong_server/server/gamestate/public/ai/auto_cut_ai.py`
  - `open_mahjong_server/server/gamestate/public/ai/smart_bot_ai.py`
  - `open_mahjong_server/server/gamestate/public/ai/smart_bot_logic.py`
  - `open_mahjong_server/server/gamestate/public/ai/get_action.py`
- Qingque and Guobiao use the shared `public.ai.smart_bot_ai`.
- Riichi has a separate smart bot path.

Why direct reuse is not currently smooth:

- Existing bots submit old-style action fields:
  - `TileId`
  - `cutIndex`
  - `cutClass`
- Existing bots expect old-style statuses:
  - `waiting_hand_action`
  - `waiting_action_after_cut`
  - `onlycut_after_action`
  - `waiting_action_qianggang`
- New-rule internals currently use:
  - `waiting_discard_response`
  - `waiting_only_cut`
  - `waiting_rob_kong`
  - `tile_id`
  - `cut_index`

## Key Architectural Lesson

The earlier implementation correctly focused on new-rule rule semantics and Python tests, but it did not preserve enough of the old project protocol surface.

Better target now:

- Keep the rule logic independent.
- Make public status names/action fields look like Qingque/Guobiao/Sichuan wherever possible.
- Reduce Unity bridge special-casing.
- Make original bot pipeline easier to reuse.

Protocol alignment plan:

- `other/new_rule_protocol_alignment_plan.md`

Primary mapping to pursue:

| Current new-rule status | Target old-style status |
| --- | --- |
| `waiting_discard_response` | `waiting_action_after_cut` |
| `waiting_only_cut` | `onlycut_after_action` |
| `waiting_rob_kong` | `waiting_action_qianggang` |
| `waiting_hand_action` | `waiting_hand_action` |
| `END` | `END` |

Primary action field mapping:

| Current field | Target old-style field |
| --- | --- |
| `tile_id` | `TileId` |
| `cut_index` | `cutIndex` |
| inferred cut class | `cutClass` |
| `target_tile` | `target_tile` |

## Next Recommended Work Route

Do not immediately add more Unity bridge patches unless a tiny retest fix is needed. First align protocol.

Recommended route:

1. Add compatibility helpers for new-rule action/status data.
   - Accept both old and new cut fields.
   - Emit old-style fields at public boundaries.
   - Keep snake-case aliases temporarily.
2. Migrate queued cut action data.
   - Include `TileId`, `cutIndex`, `cutClass`.
   - Keep `tile_id`, `cut_index` until tests/Unity are stable.
3. Migrate public status names.
   - `waiting_discard_response` -> `waiting_action_after_cut`
   - `waiting_only_cut` -> `onlycut_after_action`
   - `waiting_rob_kong` -> `waiting_action_qianggang`
4. Update new-rule tests.
5. Run backend tests.
6. Run Unity smoke.
7. Only then replace temporary synchronous bots with old-style async scheduled bot actions.

Suggested first code files for protocol alignment:

- `open_mahjong_server/server/gamestate/game_new_rule/NewRuleGameState.py`
- `open_mahjong_server/server/gamestate/game_new_rule/get_action.py`
- `open_mahjong_server/server/gamestate/game_new_rule/boardcast.py`
- `open_mahjong_server/server/gamestate/game_new_rule/test_new_rule_get_action.py`
- `open_mahjong_server/server/gamestate/game_new_rule/test_new_rule_gamestate.py`
- `open_mahjong_server/server/gamestate/game_new_rule/test_new_rule_boardcast.py`
- `open_mahjong_server/server/gamestate/game_new_rule/test_new_rule_room_creation.py`

## Unity Smoke To Run After Protocol Work

Manual flow:

1. Start backend server.
2. Open Unity Hub.
3. Open project `open_mahjong_unity`.
4. Open `Assets/Scenes/MainScene.unity`.
5. Enter Play Mode.
6. Tourist login.
7. Create hidden/dev new-rule room.
8. Add 3 bots.
9. Start game.
10. Verify table render.
11. Discard a tile.
12. If chi/cancel appears, test both paths.
13. Verify remaining tile count updates during bot turns.
14. Test or force hu if possible.
15. Let bots play to terminal state.
16. Verify final settlement/result panel appears.

Specific regressions to watch:

- Unknown message type popup.
- Cannot discard after cancel.
- Chi prompt appears but chi does not render.
- Result panel missing at wall exhaustion.
- Result panel missing at 3 winners.
- Remain tile count stale during bot-only turns.
- Bot actions too instant after async bot work.
- 0-point hu crashes or fails to display.

## Dirty Working Tree Reminder

The current working tree has many changes and untracked files. Important categories:

- New backend packages under:
  - `open_mahjong_server/server/game_calculation/new_rule/`
  - `open_mahjong_server/server/gamestate/game_new_rule/`
- New rule/reference docs under `other/`.
- Unity bridge changes under `open_mahjong_unity/Assets/Scripts/...`.
- Unity project/package settings changed after opening/installing editor packages.
- `open_mahjong_server/server/chat_server/secret_key.txt` is modified; treat carefully and do not publish secrets accidentally.
- Batchmode log files are untracked.

Before making a real commit/PR, decide whether to:

- split docs/code/Unity settings into separate commits;
- ignore or remove generated Unity logs;
- review Unity project settings changes caused by editor/package upgrades;
- handle `secret_key.txt` safely.

## Current Priority

Priority 1:

- Protocol alignment plan implementation.

Priority 2:

- Re-run backend tests and Unity smoke.

Priority 3:

- Replace temporary bot fallback with async bot scheduling and original bot logic reuse where safe.

Priority 4:

- Polish Unity result display, fan-name localization, and next-hand/game-end flow.
