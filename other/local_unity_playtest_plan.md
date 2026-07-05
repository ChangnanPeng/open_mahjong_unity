# Local Unity Playtest Plan

Last updated: 2026-07-05.

This document records the local playtest path for `open_mahjong_unity`, from the original project baseline to the new-rule Unity smoke test.

## Current Snapshot

Overall status:

- Phase 1 original Unity baseline is complete.
- Phase 2 Python new-rule backend safety net is in place and passing at component level.
- Phase 3 new-rule Unity bridge is implemented enough to start a local new-rule room from Unity.
- Current active work is Unity playtesting and fixing bridge issues found during real interaction.

Current local backend:

- Backend root: `C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server`
- Server command: `.\.venv\Scripts\python.exe main.py`
- Game WebSocket: `ws://localhost:8081/game`
- Chat WebSocket: `ws://localhost:8083/chat`
- PostgreSQL database: `open_mahjong`
- Local PostgreSQL user/password in `server/test_config.py`: `postgres` / `qwe123`

Current Unity project:

- Unity root: `C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_unity`
- Main scene: `Assets/Scenes/MainScene.unity`
- Installed editor used for playtest: Unity `6000.5.2f1`
- Unity Personal license is active.
- Unity Editor local URLs are forced to localhost by `Assets/Scripts/Config/ConfigManager.cs`.

## Phase 1: Original Unity Baseline

Status: complete.

Goal:

- Prove the local server, database, login/session, room creation, bot flow, and Unity table rendering work before blaming any new-rule issue.

Completed checks:

- PostgreSQL 18 installed and running.
- Database `open_mahjong` exists.
- Python server imports and starts.
- WebSocket smoke for existing Qingque rule passed.
- Unity opens `Assets/Scenes/MainScene.unity`.
- In Unity Play Mode:
  - tourist login works.
  - Qingque room creation works.
  - adding 3 bots works.
  - start game works.
  - table renders.
  - discarding works.
  - hu and scoring were also tested successfully.

Conclusion:

- Local environment is healthy.
- Future failures during `new_rule` testing should first be treated as new-rule adapter/UI issues, not generic deployment issues.

## Phase 2: Python New-Rule Backend

Status: backend implementation exists and component tests are passing.

Implemented packages:

- `open_mahjong_server/server/game_calculation/new_rule/`
- `open_mahjong_server/server/gamestate/game_new_rule/`

Rule/gameflow implemented so far:

- 136-tile wall, honors included, no flowers.
- No dingque.
- No dead wall.
- No chajiao.
- No immediate kong scoring.
- No cuohe/false-win flow.
- 0-point legal wins are allowed: a valid 4-melds-and-1-pair hand may win even with no scored fan.
- Blood-battle flow:
  - one player winning does not end the hand.
  - the hand ends when 3 players have won or the wall is exhausted.
- Fixed dealer rotation between hands.
- Fixed next-seat chi:
  - only the physical next seat may chi.
  - if that player has already won and exited, the next active player still may not chi.
- Same-tile discard-win lockout:
  - skipping a legal discard win records that tile.
  - the lockout applies to later discard wins and robbing-kong wins on the same tile.
  - self-draw is not restricted.
  - the player's next discard clears previous lockout state and starts a new lockout for the discarded tile.
  - multiple locked tiles may accumulate before the next discard.
- After chi/peng, the player must discard before concealed/added kong.
- Concealed kong hidden information:
  - owner sees true `G{tile}`.
  - other players see `G0` until final reveal.
- Mid-hand win details are deferred:
  - fan list, points, score changes, and full hand are hidden until final settlement.
- Score changes are deferred and applied once at final settlement.
- Multi-ron is supported.
- Stale/late actions are ignored by action tick checks.

Hidden backend integration:

- `room/create_NewRule_room` exists.
- New-rule room settings:
  - `room_rule = "new_rule"`
  - `sub_rule = "new_rule/standard"`
  - `hepai_limit = 0`
  - `open_cuohe = False`
  - `allow_spectator = False`
  - `hidden_room = True`
- Hidden rooms do not appear in the public room list.
- Generic join-by-room-id rejects hidden rooms.
- Host can recover hidden room state through `sync_my_room`.
- Host-only bot changes and start-game checks remain in force.

Useful backend test commands:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_scoring.py
.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_service.py
.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_tingpai.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_gamestate.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_action_check.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_get_action.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_boardcast.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_router.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_gamestate_manager.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_room_creation.py
```

Latest verified counts after Unity-bridge fixes:

- `test_new_rule_gamestate.py`: 55 tests
- `test_new_rule_boardcast.py`: 12 tests
- `test_new_rule_room_creation.py`: 38 tests

Note:

- The full `run_new_rule_tests.py` can be used as a broader regression command, but individual scripts have been more reliable for this local Codex shell because the full run can be slow.

Reference docs:

- `other/new_rule_work_snapshot_2026-07-05.md`
- `other/new_rule_reference.md`
- `other/new_rule_discard_win_lockout.md`
- `other/new_rule_multi_ron_implementation.md`
- `other/new_rule_fan_scoring/new_rule_fan_scoring.md`
- `other/new_rule_fan_scoring/new_rule_fan_details.md`
- `other/new_rule_implementation_plan.md`
- `other/new_rule_live_integration_boundary.md`
- `other/new_rule_unity_parity_checklist.md`
- `other/new_rule_protocol_alignment_plan.md`

## Phase 3: New-Rule Unity Bridge

Status: implemented for first playable smoke; still under active playtest.

Design choice:

- Keep the Python backend as the source of truth.
- Add Unity-compatible payloads for `new_rule`.
- Route those payloads into the existing normal table UI instead of building a new Unity table.
- Keep the rule hidden/dev-only until the local playtest loop is reliable.

Unity create-room bridge:

- The create-room UI dynamically adds a dev option named `新规则测试`.
- Selecting it sends `room/create_NewRule_room`.
- Relevant files:
  - `open_mahjong_unity/Assets/Scripts/Room/CreateRoomPanel/CreatePanel.cs`
  - `open_mahjong_unity/Assets/Scripts/Network/RoomNetworkManager.cs`

Unity message routing:

- `GameStateNetworkManager.cs` handles:
  - `gamestate/new_rule/game_start`
  - `gamestate/new_rule/broadcast_hand_action`
  - `gamestate/new_rule/ask_other_action`
  - `gamestate/new_rule/do_action`
  - `gamestate/new_rule/show_result`
  - `gamestate/new_rule/final_settlement`
  - `gamestate/new_rule/ask_action`
  - `gamestate/new_rule/reconnect`
- `NetworkManager.cs` classifies `gamestate/new_rule/...` messages as game-state messages.
- When the active room rule is `new_rule`, Unity sends:
  - `gamestate/new_rule/cut_tile`
  - `gamestate/new_rule/send_action`

Backend Unity-compatible payload bridge:

- Backend keeps lightweight test payloads under `game_info`.
- Backend also adds `unity_game_info`, shaped like Unity's existing `GameInfo`.
- `ask_action` payloads include:
  - `ask_hand_action_info`, or
  - `ask_other_action_info`
- Visible actions include `do_action_info`.
- Unity bridge handler initializes/updates the normal table from `unity_game_info`.

Temporary bot behavior for first playtest:

- Bots pass when `pass` is legal.
- Bots discard the first hand tile when `cut` is legal.
- Bots do not proactively hu or claim.
- This is intentional for the first playable smoke, not the final AI behavior.
- Unity parity and bot integration tracking lives in:
  - `other/new_rule_unity_parity_checklist.md`
  - `other/new_rule_protocol_alignment_plan.md`
- Next architecture step: align new-rule public status names and action fields with the existing Qingque/Guobiao/Sichuan protocol before doing a large bot-specific adapter.

Unity compile status:

- Batchmode compile passed with Unity `6000.5.2f1`.
- Latest relevant log:
  - `unity_batchmode_check_new_rule_network_dispatch.log`
  - result: `Exiting batchmode successfully now!`

## Unity Playtest Issues Already Found

Issue 1: start-game popup said "unknown message type".

- Cause: top-level Unity `NetworkManager` did not classify `gamestate/new_rule/...` as game-state messages.
- Fix: add `new_rule` message cases before delegating to `GameStateNetworkManager`.
- Status: fixed.

Issue 2: after the first discard, Unity showed `吃/取消`; after choosing cancel, the player could not discard.

- Cause: visible `do_action` payloads were built per viewer but did not include `player_index`, so the live send queue skipped them.
- Fix:
  - `emit_visible_action_payloads(...)` now addresses each per-viewer payload.
  - discard-resolution draws now emit `deal_tile` before the next ask window.
  - the drawn tile is visible only to the drawing player.
- Status: fixed.

Issue 3: choosing `吃` did not visibly perform chi.

- Cause:
  - Python claim result changed state, but the visible `do_action` bridge did not emit Unity-compatible `combination_mask`.
  - live-loop code looked for `result`, while discard-claim windows store `claim_result`.
- Fix:
  - `resolve_discard_claim_responses(...)` returns `combination_mask`.
  - `_apply_discard_claim(...)` stores `combination_mask` on the player.
  - `apply_action_results(...)` emits claim `do_action` payloads from `claim_result`.
- Important Unity adaptation note:
  - chi/peng/ming-gang payloads need both `combination_target` and `combination_mask`.
  - Unity uses `combination_mask` to remove hand tiles and render the meld.
- Status: fixed in code; needs Unity re-test.

Issue 4: after a new-rule hand ended, Unity did not show round settlement; remaining tile display could stay stale during bot-only turns.

- Cause:
  - backend terminal payload used `gamestate/new_rule/final_settlement`, but it did not include Unity's normal `show_result_info`, so Unity routed the message to result handling and then returned because there was no result body.
  - Unity's remaining-tile display mostly relied on local `deal_tile` decrement and ask-hand payloads; bot-only fast-forward turns could leave the displayed count stale.
- Fix:
  - `final_settlement_payload(...)` now includes a Unity-compatible `show_result_info`.
  - if the hand ends by wins, the result payload focuses on the last winner and includes final `player_to_score` plus total `score_changes`.
  - if the hand ends by wall exhaustion without wins, the result payload uses `hu_class = "liuju"`.
  - Unity now syncs `remainTiles` from `unity_game_info.tile_count` for new-rule bridge messages, and corrects the count after `do_action`.
- Status: fixed in code; needs Unity re-test.

## Current Immediate Test Flow

Use this exact flow for the next Unity smoke:

1. Ensure PostgreSQL is running.
2. Start backend:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe main.py
```

3. Open Unity Hub.
4. Open project:

```text
C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_unity
```

5. Open scene:

```text
Assets/Scenes/MainScene.unity
```

6. Enter Play Mode.
7. Tourist login.
8. Create `新规则测试` room.
9. Add 3 bots.
10. Start game.
11. Confirm table renders.
12. Discard one tile.
13. If `吃/取消` appears, test both:
    - choose `取消`, then confirm the next self turn can discard.
    - choose `吃`, then confirm the meld appears and the chi player enters discard state.
14. Continue until at least one of these is observed:
    - multiple normal turns progress.
    - chi/peng/gang prompt works.
    - hu prompt works.
    - final settlement appears.

Expected minimum pass:

- New-rule room starts from Unity.
- Table renders.
- Current player can discard.
- Canceling a response prompt does not freeze the hand.
- Choosing chi visibly performs the meld and continues to discard.
- When the wall is exhausted or the third player wins, a round settlement panel appears.
- Remaining tile display reaches 0 at wall exhaustion.

Better pass:

- One win does not end the hand immediately.
- Mid-hand win details remain hidden.
- Final settlement reveals deferred details.
- Self-draw, discard win, multi-ron, concealed kong, added kong, robbing kong, and wall exhaustion can each be tested later.

## If The Next Unity Smoke Fails

Inspect in this order:

1. Unity Console error.
2. Backend terminal/log error.
3. Whether the message type is routed by `NetworkManager.cs`.
4. Whether `GameStateNetworkManager.cs` has a handler for the payload.
5. Whether `unity_game_info` has the fields Unity expects.
6. For visible table updates, inspect `do_action_info`:
   - discard needs `cut_tile`.
   - draw needs `deal_tile`.
   - chi/peng/ming-gang need `combination_target` and `combination_mask`.
   - concealed kong must hide true tile from non-owner viewers.
7. For action buttons, inspect `ask_hand_action_info` or `ask_other_action_info`:
   - `action_list`
   - `action_tick`
   - `cut_tile`
   - chi candidate / combo data if needed.

## Work Deferred Until After Playable Smoke

Do not spend time on these until the new-rule local loop is reliable:

- Public room-list exposure.
- Polished official create-room UI.
- Spectator support.
- Record/history support.
- Statistics integration.
- Rule help screens.
- Full fan-name localization in Unity.
- Full result-panel polish for all edge cases.
- Replacing temporary bot behavior with original project AI or a rule-aware new-rule AI.

## Final Productization Later

After local Unity playtest succeeds:

1. Decide how new-rule rooms should appear in the normal UI.
2. Decide whether hidden/dev route should remain available.
3. Add official room creation settings.
4. Add Unity display names and fan-name mapping.
5. Add record/replay support.
6. Add spectator/reconnect polish.
7. Run regression on existing rules: Qingque, Guobiao, Sichuan, Classical, Riichi.
