# Local Unity Playtest Plan

Last updated: 2026-07-06.

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

## Local Ops Quick Reference

Use these commands when resuming Unity playtests after context compression. Keep shared behavior aligned with existing rules: the backend owns timeout/default action behavior; Unity timeout handling should stay UI/input cleanup unless old rules do the same thing.

### Identify Python servers

Prefer checking command lines before stopping anything. Multiple Python processes may exist; the local game server is the one whose command line contains both `open_mahjong_server` and `main.py`.

```powershell
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Where-Object { $_.CommandLine -match 'open_mahjong_server' } | Select-Object ProcessId,CommandLine
```

If `py.exe` was used:

```powershell
Get-CimInstance Win32_Process -Filter "name = 'py.exe'" | Where-Object { $_.CommandLine -match 'open_mahjong_server' } | Select-Object ProcessId,CommandLine
```

### Restart Python server

Stop only the confirmed local server PID:

```powershell
Stop-Process -Id <pid> -Force
```

Start it in the foreground for readable logs:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe main.py
```

Or start it hidden for Unity playtesting:

```powershell
Start-Process -WindowStyle Hidden -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "main.py" -WorkingDirectory "C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server"
```

If backend tests print `logs/app.log` rollover errors while the server is running, treat that as log-file contention noise unless the test exit code fails.

### Unity batchmode compile

Use the installed editor path:

```powershell
& 'C:\Program Files\Unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe' -batchmode -quit -projectPath 'C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_unity' -logFile 'C:\Users\changnan\Documents\open_mahjong_unity\unity_batchmode_check_current.log'
```

Check compile status:

```powershell
Select-String -Path C:\Users\changnan\Documents\open_mahjong_unity\unity_batchmode_check_current.log -Pattern "Tundra build success|error CS|Compilation failed|Tundra build failed|Scripts have compiler errors|Exiting batchmode"
Get-Content C:\Users\changnan\Documents\open_mahjong_unity\unity_batchmode_check_current.log -Tail 80
```

### Unity Editor state

List Unity processes and distinguish the user's Editor from Codex batchmode by command line. A process with `-batchmode` / `-batchMode` is a compile/import worker; a normal Editor usually has no batchmode flag.

```powershell
Get-CimInstance Win32_Process -Filter "name = 'Unity.exe'" | Select-Object ProcessId,CommandLine
```

If batchmode has already logged `Tundra build success` but does not exit, stop only the confirmed batchmode PIDs, not a normal interactive Editor PID:

```powershell
Stop-Process -Id <batchmode-pid> -Force
```

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
- `other/new_rule_legacy_alignment_refactor_plan.md`
- `other/new_rule_fan_scoring/new_rule_fan_scoring.md`
- `other/new_rule_fan_scoring/new_rule_fan_details.md`
- `other/new_rule_implementation_plan.md`
- `other/new_rule_live_integration_boundary.md`
- `other/new_rule_unity_parity_checklist.md`
- `other/new_rule_protocol_alignment_plan.md`
- `other/new_rule_debug_scenario_plan.md`

## Phase 3: New-Rule Unity Bridge

Status: implemented for first playable smoke; still under active playtest.

Rare-event debug status:

- Backend dev scenario injection has been added for `multi_ron_2`, `multi_ron_3`, `rob_kong`, `rob_kong_multi_ron_2`, `haitei`, `houtei`, `rinshan`, `heavenly_win`, `earthly_win`, and `nine_gates`.
- Route: `gamestate/new_rule/debug_scenario`, host-only, new-rule-only.
- Tests are covered by `server/gamestate/game_new_rule/test_new_rule_debug_scenarios.py`, router tests, and `run_new_rule_tests.py`.
- Unity table UI now shows a small runtime-created `NR Debug` floating button for all implemented debug scenarios.
- The backend route now cancels the active live loop before injection and starts a dev-only scenario loop, so scenario injection does not race an already-waiting live action window.
- Next manual step: start a new-rule room, use the in-game `NR Debug` floating button, trigger each scenario, and verify the real Unity flow.
- Detailed plan and cleanup steps are in `other/new_rule_debug_scenario_plan.md`.

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

Issue 5: other players' mid-hand self-draw win tile could fail to move into the exposed/win area, sometimes leaving a blank face-up hidden tile in the draw slot.

- Symptom:
  - In blood-battle continuation, when another player self-drew and won mid-hand, Unity sometimes showed no flying win tile.
  - In the bad visual state, the hidden drawn tile could remain near that player's draw slot and appear as a blank face-up tile instead of moving face-down into the win/exposed area.
- Cause:
  - New-rule mid-hand self-draw hides the real winning tile from non-winners, so Unity receives `hu_self` with the real tile omitted for other viewers (`tile = null`, `hepai_tile = 0`).
  - The backend can immediately continue the hand by sending the next player's draw/ask messages after the mid-hand `show_result`.
  - Unity was using `RoundEndPresentation` as the coroutine host for the short mid-hand win-tile animation. The next ask/resume path could call `StopActiveSequence()` before `CoAnimateTileToBuhua` finished, cutting off the tile flight.
  - The other-player draw animation can also materialize one frame later than the `hu_self`/`show_result` pair, so taking "last hand child" was not always the same as taking the draw-slot tile.
- Fix:
  - For `new_rule`, `TryResumeAfterSichuanContinue()` no longer stops the active `RoundEndPresentation` sequence during mid-hand continuation; it only clears the temporary result panel state and lets the 3D win-tile animation finish.
  - Other-player new-rule self-draw presentation suppresses the next draw-slot spawn while the hidden win tile is being moved.
  - The 3D presentation selects the draw-slot tile by seat direction, not by blindly taking the last hand child.
  - If no draw-slot object exists yet, it spawns a hidden fallback tile at the expected draw-slot pose and still animates it into the win/exposed area.
- Review notes:
  - Do not reveal other players' real self-draw tile for new-rule mid-hand wins; the fix is Unity-side presentation of a hidden tile, not backend disclosure.
  - The `StopActiveSequence()` exception is new-rule-specific because old Sichuan mid-hand/result flow uses that presentation runner differently.
  - Be careful when reusing result/round-end coroutine hosts for short in-hand animations; later table messages may arrive while the animation is still running.
- Verification:
  - Temporary logs with tag `[TEMP NewRuleZimoDebug]` showed the failing path previously stopped after `CoAnimateTileToBuhua lerp`.
  - After the fix, the same flow reached `CoAnimateTileToBuhua complete` and `zimo animate done` even when a later `broadcast_hand_action` had already arrived.
  - The temporary logs were removed after verification.
- Status: fixed and Unity-playtested; batchmode compile passed after cleanup.

Issue 6: robbing-kong double-win and other multi-win presentation copies could show a blank or wrong tile face.

- Symptom:
  - In the new-rule robbing-kong double-win debug scenario, the first winner's flying win tile could appear as a blank tile.
  - An earlier attempted fix cloned `lastCutJiagang3DObject`, but that could show the wrong tile face, apparently carrying stale material/logical state from an unrelated hand tile.
- Cause:
  - Multi-win presentation sometimes needs an extra visible copy of the same winning tile.
  - This is expected for ordinary multi-ron too: the first displayed winner cannot consume the real river discard, because later winners still need the same source tile.
  - It is especially easy to hit in robbing-kong double wins, where all four physical copies may already be represented by the hand/meld/added-kong attempt.
  - `MahjongObjectPool.Spawn(hepai_tile, ...)` only has four real objects per standard tile. If all are in use, it returns null.
  - The old fallback used `SpawnBlankTile(..., logicalTileId)`, which preserves the logical id for bookkeeping but intentionally keeps the blank face, so the flying presentation tile was blank.
  - Cloning the visible added-kong object was also wrong, because it bypassed `ApplyCardTexture(...)` and could carry stale rendered face state.
- Fix:
  - Added `MahjongObjectPool.SpawnVisibleTileFromBlankFallback(...)`.
  - This uses a blank-pool object as the carrier, applies the requested `hepai_tile` texture, sets the logical tile id to the winning tile, and sets the pool-return id to the blank pool.
  - Updated the Sichuan/new-rule multi-ron presentation fallback path (`SpawnSichuanRonPresentTile`) to use this visible-blank fallback when the real tile pool is exhausted.
  - Kept the actual final-source handling unchanged: the last multi-ron panel still consumes/recycles the real discard or added-kong source where appropriate.
- Review notes:
  - Do not use this fallback for ordinary chi/peng/kong meld construction by default. Melds are real physical tile groups; if they need a fifth real tile object, that usually indicates a return-order or state-sync bug that should be exposed and fixed.
  - This fallback is appropriate for presentation-only duplicate win tiles, because the UI is intentionally showing an extra copy of one source tile.
  - Do not clone the source tile to solve this; material/logical state can be stale unless the texture is explicitly reapplied.
- Verification:
  - Robbing-kong double-win Unity playtest passed after this change.
  - Unity batchmode script compilation passed after adding the fallback method; only existing warnings were present.
- Status: fixed and Unity-playtested for robbing-kong double-win. Ordinary multi-ron should be covered by the same shared presentation path but should still be checked when a natural/manual repro is available.

Issue 7: mid-hand multi-win presentation needed pacing between result panels.

- Symptom:
  - In new-rule blood-battle continuation, multiple mid-hand win presentations could arrive back-to-back.
  - Earlier playtests showed the first flying win tile/panel could be interrupted or visually incomplete before the next winner panel or continuation draw arrived.
  - A conservative delay of `1.5s` worked, but felt too slow during repeated debug-scenario testing.
- Cause:
  - The Unity presentation path is Sichuan-style: one short active win presentation coroutine handles the flying tile and temporary panel state.
  - If the backend immediately sends the next `show_result`, `deal_tile`, or ask-action message, Unity may advance/resume the table state while the previous presentation is still running.
  - Sichuan avoids this by waiting after each mid-hand win presentation before sending the next continuation message.
- Fix:
  - New-rule backend now mirrors the Sichuan timing shape by inserting an internal outbound marker after each deferred mid-hand `show_result`.
  - `NewRuleGameState.flush_outbound_payloads()` consumes the marker locally and sleeps; the marker is never sent to Unity.
  - The current delay is `NEW_RULE_MID_HU_ANIM_SECONDS = 0.5`.
  - This keeps the protocol clean: Unity still receives normal `show_result` / `do_action` / `deal_tile` messages, while the backend controls pacing like the existing Sichuan flow.
- Why `0.5s` is acceptable for now:
  - The win-tile travel animation currently uses about `0.2s`, so `0.5s` leaves a small buffer for coroutine scheduling and table UI updates.
  - Manual Unity playtest with robbing-kong double-win passed at `0.5s`.
  - The shorter delay makes multi-panel debug testing less sluggish than the earlier `1.5s` value.
- Risk / rollback:
  - `0.5s` is intentionally less conservative than Sichuan's `1.5s`.
  - If low-frame-rate playtests, heavier scenes, or slower machines again show interrupted flying tiles/panels, raise the value to `0.75s`, `1.0s`, or ultimately the Sichuan-style `1.5s`.
  - Do not solve this by sending custom Unity messages or adding frontend-only timeouts; the cleaner alignment is backend pacing between ordinary protocol messages.
- Verification:
  - Backend tests cover the internal delay marker ordering: first mid-hand panel, then delay marker, then next panel/continuation.
  - Focused and full new-rule backend test suites passed after changing the delay to `0.5s`.
  - Unity playtest confirmed `0.5s` works for the robbing-kong double-win scenario.
- Status: fixed and Unity-playtested at `0.5s`; keep an eye on slower-machine or heavier-scene regressions.

Issue 8: same-tile discard-win lockout needed deterministic rare-event coverage.

- Requirement:
  - Passing a discard win locks that same tile until the player next discards.
  - Self-draw ignores the lock.
  - The next discard clears the old lock and starts the new lock on the discarded tile.
  - The lock must persist through intervening claims by other players.
  - Robbing an added kong is discard-win-like and is also blocked by the same-tile lock.
- Implemented coverage:
  - Unity-visible `same_tile_lockout` debug scenario covers pass -> self-draw still offered -> cutting the same tile keeps the next same-tile ron blocked.
  - The same scenario also covers pass -> cutting a different tile -> next same-tile discard can be won.
  - Backend deterministic tests cover immediate next-bot same-tile discard, pong-then-later-same-tile discard, and pong-chain-then-added-kong where robbing kong is blocked.
- Verification:
  - Manual Unity playtest passed for both visible `same_tile_lockout` branches.
  - `server/gamestate/game_new_rule/test_new_rule_debug_scenarios.py` passed with 17 tests.
  - `run_new_rule_tests.py` passed with 11 scripts.
- Review notes:
  - Robbing-kong lockout is a real reachable sequence: another player may pong the tile that player 0 passed on, then later draw the fourth copy and attempt added kong.
  - Ordinary bots are not deterministic enough to manually reproduce the pong-chain branches. Add separate scripted Unity debug buttons only if visual coverage for those chains becomes necessary.
- Status: fixed and Unity-playtested for the visible branches; deeper chain branches are backend-tested.

Protocol note: `hu_first` / `hu_second` / `hu_third` can appear on single discard wins.

- These names follow the existing Guobiao/Qingque/Classical/Riichi-style Unity protocol.
- They are relative-seat ron classes from the discarder/kong player, not ordinal winner numbers in one multi-ron event.
- From the discarder/kong player:
  - next seat -> `hu_first`
  - opposite seat -> `hu_second`
  - previous seat -> `hu_third`
- Therefore a single winner can correctly be reported as `hu_third` if that winner is in the previous-seat slot relative to the discarder.
- New-rule backend should keep this mapping for Unity compatibility, while still using explicit `hepai_player_index` for the actual winner identity.

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
