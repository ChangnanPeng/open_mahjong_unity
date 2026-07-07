# New Rule Legacy Alignment Refactor Plan

Last updated: 2026-07-05.

Purpose: plan a careful audit and refactor that makes the Python `new_rule` implementation align as closely as possible with existing Qingque/Guobiao/Sichuan variable names, data shapes, interfaces, Unity expectations, bot hooks, record/replay format, and database storage conventions.

This is the next major work route after snapshot commit `cface9e5` on branch `codex/new-rule-work-snapshot-2026-07-05`.

Related docs:

- `other/new_rule_work_snapshot_2026-07-05.md`
- `other/new_rule_protocol_alignment_plan.md`
- `other/new_rule_unity_parity_checklist.md`
- `other/local_unity_playtest_plan.md`
- `other/new_rule_legacy_alignment_audit.md`

## Guiding Principle

Keep new-rule game semantics independent, but make its public surface look like existing rules.

In practice:

- Rule decisions stay in `game_new_rule`.
- Fan/scoring stays in `game_calculation/new_rule`.
- Public statuses, action dictionaries, broadcast payloads, game records, bot entrypoints, and room/database wiring should follow Qingque/Guobiao/Sichuan conventions unless there is a concrete new-rule reason not to.

This refactor is not cosmetic. It is intended to reduce Unity special cases, enable original bot reuse, make replay/record storage work naturally, and make future maintenance less surprising.

## Clean Refactor Requirement

The final code should not keep a compatibility layer for the earlier `new_rule` prototype shape.

Final target:

- One canonical status vocabulary: the existing-rule style.
- One canonical action-data shape: the existing-rule style.
- No long-term `tile_id` / `cut_index` aliases for cut actions.
- No long-term `waiting_discard_response` / `waiting_only_cut` / `waiting_rob_kong` aliases.
- No bridge code whose only purpose is to support the abandoned prototype protocol.
- Tests should assert the final canonical interface, not both old and prototype variants.

Temporary migration scaffolding is acceptable only inside a small, local edit while tests are being moved. It should be removed before the phase is considered complete and before any review-quality commit is made.

## Baseline References

Primary references:

- Qingque:
  - `open_mahjong_server/server/gamestate/game_mmcr/QingqueGameState.py`
  - `open_mahjong_server/server/gamestate/game_mmcr/wait_action.py`
  - `open_mahjong_server/server/gamestate/game_mmcr/boardcast.py`
  - `open_mahjong_server/server/database/qingque/store_qingque.py`
- Guobiao:
  - `open_mahjong_server/server/gamestate/game_guobiao/GuobiaoGameState.py`
  - `open_mahjong_server/server/gamestate/game_guobiao/wait_action.py`
  - `open_mahjong_server/server/gamestate/game_guobiao/boardcast.py`
  - `open_mahjong_server/server/database/guobiao/store_guobiao.py`
- Sichuan:
  - `open_mahjong_server/server/gamestate/game_sichuan/SichuanGameState.py`
  - `open_mahjong_server/server/gamestate/game_sichuan/wait_action.py`
  - `open_mahjong_server/server/gamestate/game_sichuan/boardcast.py`
  - `open_mahjong_server/server/database/sichuan/store_sichuan.py`

Shared infrastructure references:

- `open_mahjong_server/server/gamestate/public/game_record_manager.py`
- `open_mahjong_server/server/gamestate/public/spectator_manager.py`
- `open_mahjong_server/server/gamestate/public/ready_phase.py`
- `open_mahjong_server/server/gamestate/public/next_game_round.py`
- `open_mahjong_server/server/gamestate/public/ai/auto_cut_ai.py`
- `open_mahjong_server/server/gamestate/public/ai/smart_bot_ai.py`
- `open_mahjong_server/server/gamestate/public/ai/get_action.py`
- `open_mahjong_server/server/database/db_manager.py`
- `open_mahjong_unity/Assets/Scripts/Network/Serialize/Response.cs`
- `open_mahjong_unity/Assets/Scripts/Network/GameStateNetworkManager.cs`
- `open_mahjong_unity/Assets/Scripts/GameScene/GameStateManager/GameRecordManager/`

## Current Known Misalignment

Status names:

| Current `new_rule` | Existing-rule convention |
| --- | --- |
| `waiting_discard_response` | `waiting_action_after_cut` |
| `waiting_only_cut` | `onlycut_after_action` |
| `waiting_rob_kong` | `waiting_action_qianggang` |
| custom terminal/final-settlement flow | existing `END` + `show_result` / record round-end conventions |

Action fields:

| Current `new_rule` | Existing-rule convention |
| --- | --- |
| `tile_id` | `TileId` |
| `cut_index` | `cutIndex` |
| implicit cut class | `cutClass` |
| custom queued action result fields | old `action_dict`/`action_data` style |

Broadcast/Unity:

- Historical start-of-refactor state: new rule relied on `unity_game_info` bridge payloads.
- Current state after Phase 4b: `unity_game_info` has been removed and normal `game_info` is canonical for new-rule Unity messages.
- Unity has explicit `gamestate/new_rule/...` cases.
- Some bridge code was added because payloads were not originally shaped like old `GameInfo`, `AskHandActionGBInfo`, `AskOtherActionGBInfo`, `DoActionInfo`, and `ShowResultInfo`.

Bot baseline at the start of this refactor:

- New-rule bots used synchronous fallback `_default_bot_action`.
- Existing bots expected old statuses and old cut fields.
- Qingque and Guobiao share the existing smart bot path; new rule needed to get closer to that path before writing a large adapter.

Current bot state after Phase 6a:

- `_default_bot_action` has been removed.
- New rule uses `game_new_rule/bot.py` as a thin async adapter.
- The adapter reuses shared smart-bot scoring helpers but submits through new-rule validation.

Record/replay/database:

- Existing rules use `init_game_record`, `init_game_round`, `player_action_record_*`, `player_action_record_round_end`, and `end_game_record`.
- Existing record storage writes `game_records` and `game_player_records`.
- Unity record/replay relies on `action_ticks` shape, `game_title`, round metadata, `cut_tile_index`, meld masks, and score changes.
- New rule needs an explicit alignment audit before claiming record/replay support.

## Non-Negotiable New-Rule Semantics

The refactor must not change these:

- 136-tile wall; honors included; no flowers.
- No dead wall.
- No dingque.
- No chajiao.
- No immediate kong scoring.
- No cuohe/false-win.
- 0-point legal win is allowed.
- Blood-battle flow: hand continues after one win.
- Hand ends at 3 winners or wall exhaustion.
- Fixed dealer rotation each hand.
- Chi only by physical next seat, not next active player.
- After chi/peng, player must discard before concealed/added kong.
- Same-tile discard-win lockout, including robbed-kong hu.
- Concealed kong tile hidden from other players until final reveal.
- Mid-hand hu hides fan list and score changes; final settlement reveals them.

## Phase 0: Safety And Branch Setup

Goal: protect the current snapshot and avoid mixing unrelated local files into the refactor.

Tasks:

- [x] Snapshot commit exists: `cface9e5`.
- [ ] Create a new branch from snapshot before edits, for example `codex/new-rule-legacy-alignment`.
- [ ] Keep `open_mahjong_server/server/chat_server/secret_key.txt` out of commits.
- [ ] Keep `unity_batchmode_check*.log` out of commits unless intentionally archived.
- [ ] Consider adding/confirming ignore rules for local Unity logs if needed.
- [ ] Before starting code edits, run the current new-rule backend tests once to establish the starting failure/pass baseline.

Suggested baseline commands:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_scoring.py
.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_service.py
.\.venv\Scripts\python.exe server\game_calculation\new_rule\test_new_rule_tingpai.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_action_check.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_get_action.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_boardcast.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_gamestate.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_router.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_gamestate_manager.py
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_room_creation.py
```

## Phase 1: Interface Inventory

Goal: produce a precise mapping before changing code.

Audit targets:

- [ ] `game_status` reads/writes in `game_new_rule`.
- [ ] `action_dict` shape and lifecycle.
- [ ] `waiting_players_list` lifecycle.
- [ ] queued action data shape.
- [ ] `submit_action`, `get_action`, `get_ai_action`, room router payload handling.
- [ ] `broadcast_ask_hand_action`, `broadcast_ask_other_action`, `broadcast_do_action`, `final_settlement_payload`, reconnect handling.
- [ ] Unity `Response.cs` DTO fields currently consumed.
- [ ] Unity `GameStateNetworkManager.cs` special cases for `new_rule`.
- [ ] game record ticks and round metadata.
- [ ] database storage and player stats/fan stats expectations.
- [ ] bot scheduling and action-submission expectations.

Deliverable:

- [x] Add an "Audit Matrix" section to this plan or a separate `other/new_rule_legacy_alignment_audit.md`.
- [ ] For each mismatch, mark one of:
  - rename to old convention;
  - keep new name because rule-specific behavior requires it;
  - remove because bridge workaround becomes unnecessary.

## Phase 2: Canonical Action Data Rewrite

Goal: rewrite action payloads to the existing-rule canonical shape without keeping prototype aliases.

Reason:

- Action field rewrite is lower risk than status renaming.
- It lets Unity, tests, and bots use the same fields as existing rules.
- A clean single-shape action dictionary is easier to review than a compatibility layer.

Tasks:

- [x] Decide whether a small protocol/constants module improves clarity. Decision: not needed for Phase 2; direct canonical field usage is clearer.
- [ ] Implement helpers:
  - `get_action_type(action_data)`
  - `get_cut_tile(action_data)`
  - `get_cut_index(action_data)`
  - `get_cut_class(action_data, player=None)`
  - `make_cut_action(tile_id, cut_index, cut_class)`
  - `make_response_action(action_type, target_tile=None)`
- [x] Update `NewRuleGameState.submit_action(...)` to accept and store canonical action data.
- [x] Ensure queued cut actions use only:
  - `TileId`
  - `cutIndex`
  - `cutClass`
- [x] Update `get_action.py` so human and AI actions both submit canonical old-style fields.
- [x] Update `boardcast.py` to read canonical fields directly.
- [x] Update tests to assert only canonical old-style fields.
- [x] Remove prototype field names from production code:
  - `tile_id`
  - `cut_index`

Do not leave behind:

- dual reads of both `TileId` and `tile_id`;
- tests that encourage both shapes;
- comments describing the prototype field shape as still supported.

## Phase 3: Status Name Alignment

Goal: move public/live-loop status names to existing-rule conventions.

Status: complete in commit-in-progress after Phase 2.

Target mapping:

- `waiting_discard_response` -> `waiting_action_after_cut`
- `waiting_only_cut` -> `onlycut_after_action`
- `waiting_rob_kong` -> `waiting_action_qianggang`
- keep `waiting_hand_action`
- keep `waiting_ready`
- keep `END`

Tasks:

- [ ] Add status constants in `protocol.py`.
- [x] Replace string literals in `NewRuleGameState.py`.
- [x] Replace expected statuses in tests.
- [x] Update `boardcast.py` ask/reconnect behavior to use old statuses.
- [x] Update `get_action.py` validation branches.
- [x] Update any room/router tests that wait for old custom statuses.
- [x] Remove or document every remaining custom status string.
- [x] Remove prototype status aliases from production code and tests.

Verification:

- `rg -n "waiting_discard_response|waiting_only_cut|waiting_rob_kong" open_mahjong_server\server\gamestate\game_new_rule` returns no matches.
- `test_new_rule_get_action.py`: 4 tests passed.
- `test_new_rule_router.py`: 3 tests passed.
- `test_new_rule_boardcast.py`: 13 tests passed.
- `test_new_rule_gamestate.py`: 55 tests passed.
- `test_new_rule_action_check.py`: 9 tests passed.
- `test_new_rule_gamestate_manager.py`: 1 test passed.
- `test_new_rule_room_creation.py`: 38 tests passed.
- Known Windows logging rollover `PermissionError` noise still appears, but all tests exit successfully.

Important caveat:

- Sichuan's blood-battle flow uses old statuses plus rule-specific settlement steps. New rule may still need custom final-settlement state/data internally, but it should not expose custom names to Unity/bots unless unavoidable.

## Phase 4: Broadcast And Unity Payload Convergence

Goal: reduce Unity special-case code by emitting the existing payload shapes as naturally as possible.

Decision after audit:

- Do not keep `unity_game_info` long-term. New rule should put Unity-ready `GameInfo` data directly in `game_info`.
- Do not keep `gamestate/new_rule/ask_action` as the main public ask message. Split it into:
  - `gamestate/new_rule/broadcast_hand_action` for self-turn asks.
  - `gamestate/new_rule/ask_other_action` for discard/rob-kong response asks.
- Do not keep `gamestate/new_rule/final_settlement` as the public result message. Use `gamestate/new_rule/show_result` with `show_result_info`.
- `gamestate/new_rule/do_action` can remain because it already follows `DoActionInfo` closely.
- Reconnect should not use a new-rule-only public message. It should send normal `gamestate/new_rule/game_start`, then resend the pending ask with `broadcast_hand_action` / `ask_other_action`, or resend `show_result` after `END`.

Audit and align these DTOs:

- `GameInfo`
- `AskHandActionGBInfo`
- `AskOtherActionGBInfo`
- `DoActionInfo`
- `ShowResultInfo`

Tasks:

- [x] Decide whether `unity_game_info` should remain long-term or be replaced by normal `game_info` for new-rule Unity messages.
- [ ] Ensure ask-hand payload uses existing fields:
  - `action_list`
  - `action_tick`
  - `forbidden_cut_tiles`
  - hand-action tile lists as expected by Unity.
- [ ] Ensure ask-other payload uses existing fields:
  - `action_list`
  - `action_tick`
  - `cut_tile`
  - chi options / combination candidates as Unity expects.
- [ ] Ensure do-action payload uses existing fields:
  - `action_list`
  - `action_player`
  - `cut_tile`
  - `cut_tile_index`
  - `cut_class`
  - `deal_tile`
  - `combination_mask`
  - `combination_target`
- [ ] Ensure result payload uses existing `show_result_info` fields.
- [x] Keep `gamestate/new_rule/...` routes if room-rule path separation requires them.
- [x] Remove Unity bridge branches that become redundant after payload convergence.

Phase 4 implementation slices:

- Phase 4a: backend payload type/field convergence. Status: complete in commit-in-progress for public message types.
- Phase 4b: Unity C# bridge cleanup (`unity_game_info`, `ask_action`, `final_settlement` paths). Status: complete in commit-in-progress.
- Phase 4c: reconnect behavior convergence. Status: complete in commit-in-progress.

Phase 4a verification:

- `rg -n "gamestate/new_rule/ask_action|gamestate/new_rule/final_settlement" open_mahjong_server\server\gamestate\game_new_rule open_mahjong_unity\Assets\Scripts\Network` returns no matches.
- `test_new_rule_boardcast.py`: 13 tests passed.
- `test_new_rule_gamestate.py`: 55 tests passed.
- `test_new_rule_room_creation.py`: 38 tests passed.
- Known Windows logging rollover `PermissionError` noise still appears, but all tests exit successfully.

Phase 4b verification:

- `rg -n "unity_game_info|SyncNewRuleUnityGameInfo|gamestate/new_rule/ask_action|gamestate/new_rule/final_settlement" open_mahjong_server open_mahjong_unity\Assets` returns no matches.
- `test_new_rule_boardcast.py`: 13 tests passed.
- `test_new_rule_gamestate.py`: 55 tests passed.
- `test_new_rule_room_creation.py`: 38 tests passed.
- Known Windows logging rollover `PermissionError` noise still appears, but all tests exit successfully.

Phase 4c verification:

- New-rule reconnect now restores the client with normal `gamestate/new_rule/game_start`.
- If the player still has a pending hand action, reconnect resends `gamestate/new_rule/broadcast_hand_action`.
- If the player still has a pending discard/rob-kong response, reconnect resends `gamestate/new_rule/ask_other_action`.
- If the hand is already `END`, reconnect resends `gamestate/new_rule/show_result` after the restored `game_start`.
- Unity no longer dispatches or handles `gamestate/new_rule/reconnect`.
- `rg -n "gamestate/new_rule/reconnect|HandleNewRuleBridgeMessage|reconnect_payload|build_reconnect_payload" open_mahjong_server open_mahjong_unity\Assets` returns no matches.
- `test_new_rule_boardcast.py`: 15 tests passed.
- `test_new_rule_gamestate.py`: 59 tests passed.
- `test_new_rule_room_creation.py`: 38 tests passed.
- Known Windows logging rollover `PermissionError` noise still appears, but all tests exit successfully.

Unity regression targets:

- [ ] Start new-rule room.
- [ ] Discard.
- [ ] Chi/cancel.
- [ ] Peng/gang/angang/jiagang.
- [ ] Robbed kong.
- [ ] Mid-hand hu continuation.
- [ ] Wall exhaustion result.
- [ ] 3-winner result.
- [ ] Remaining tile count.

## Phase 5: Record, Replay, Spectator, And Storage Alignment

Goal: make new-rule records look like existing records so data storage, record list, replay, and spectator mode can work with minimal special casing.

Backend record tasks:

- [x] Confirm `init_game_record(self)` is used and `game_title` includes:
  - `rule`
  - `sub_rule`
  - `max_round`
  - `start_time`
  - `room_type`
  - `hepai_limit`
  - new-rule-specific flags only if needed.
- [x] Confirm each hand calls `init_game_round(self)`.
- [x] Use existing `player_action_record_deal`.
- [x] Use existing `player_action_record_cut`.
- [x] Use existing `player_action_record_angang`.
- [ ] Use existing `player_action_record_jiagang`.
- [x] Use existing `player_action_record_chipenggang`.
- [x] Use existing `player_action_record_hu` where compatible.
- [ ] Add narrowly scoped new-rule record helpers only for truly new concepts:
  - mid-hand winner exits;
  - deferred final settlement reveal;
  - same-tile lockout should probably not appear as a replay action unless useful for debugging.
- [x] Use `player_action_record_liuju` for wall exhaustion if compatible.
- [x] Use `player_action_record_round_end`.
- [x] Use `end_game_record`.
- [ ] Ensure `score_changes` are shaped by seat/original index consistently with old rules.
- [ ] Ensure `record_counter` fields are updated:
  - `zimo_times`
  - `dianhe_times`
  - `fangchong_times`
  - `fangchong_score`
  - `recorded_fans`
  - `win_score`
  - `win_turn`
  - `rank_result`

Phase 5a status:

- Minimal standard `game_record` scaffolding is now present in `NewRuleGameState`.
- The live loop initializes `game_title` and `round_index_1`, records visible cut/deal/chi/peng/gang/angang ticks, and writes final hu/liuju + `end`.
- `RecordCounter` exists for new-rule players and is updated for zimo/dianhe/fangchong/win score on final settlements.
- Storage, record list/replay validation, spectator incremental record updates, Unity multi-round manual verification, final ranks, and clean jiagang record timing are still pending.

Phase 5a verification:

- `test_new_rule_gamestate.py`: 59 tests passed.
- `test_new_rule_boardcast.py`: 15 tests passed.
- `test_new_rule_room_creation.py`: 38 tests passed.
- Known Windows logging rollover `PermissionError` noise still appears, but all tests exit successfully.

Database tasks:

- [ ] Add `server/database/new_rule/store_new_rule.py` only if reusing `store_guobiao_game_record` or `store_qingque_game_record` is not clean.
- [ ] Register storage function in `db_manager.py`.
- [ ] Decide whether new rule should write fan stats tables now or only basic `game_records` / `game_player_records`.
- [ ] Ensure `get_record_list` and `get_record_by_id` display metadata correctly for `rule = "new_rule"`.

Unity replay/spectator tasks:

- [ ] Load a new-rule record from `data/get_record_by_id`.
- [ ] Verify initial hands render.
- [ ] Verify `cut_tile_index` works during replay.
- [ ] Verify chi/peng/gang masks render.
- [ ] Verify concealed kong hidden/revealed behavior in replay.
- [ ] Verify mid-hand hu does not reveal prematurely if replaying live ticks.
- [ ] Verify final settlement reveals fan list.
- [ ] Verify score history and final score display.

## Phase 6: Bot Pipeline Alignment

Goal: replace temporary synchronous bot fallback with old-style async scheduled bot actions.

Prerequisite:

- Action fields and statuses are aligned enough that bot code does not need a large translation layer.

Tasks:

- [x] Decide whether direct import of `public.ai.auto_cut_ai.auto_cut_action` is safe after alignment.
  - Decision: not direct. The public bots import the shared old-rule `public.ai.get_action`, so new rule needs its own thin adapter that submits through `game_new_rule.get_action`.
- [x] Add a thin new-rule bot adapter: `open_mahjong_server/server/gamestate/game_new_rule/bot.py`.
- [x] Preserve old bot delay behavior for self-turn and forced-discard cuts.
- [x] Replace `_default_bot_action` synchronous fallback with async task scheduling from `wait_action`.
- [x] For `user_id == 0`, implement auto-cut/pass behavior first.
- [x] For `user_id == 2`, reuse smart discard selection helpers:
  - `count_melds`
  - `count_visible_tiles`
  - `find_best_cut`
  - `find_best_cut_score`
  - `should_accept_hu`
- [x] Make bot submissions go through new-rule validation.
- [x] Ensure stale bot actions after action-tick changes are ignored.
- [x] Ensure bot action after `END` is ignored.
- [x] Cleanup cancels pending bot tasks.
- [ ] Unity manual parity check: confirm bot discard pacing is no longer instantaneous.
- [ ] Add finer tests for smart bot chi/peng/gang and hu choices.

Tests:

- [x] auto-cut bot queues a delayed cut.
- [x] cleanup cancels pending bot tasks.
- [ ] smart bot queues a legal cut.
- [ ] bot pass after discard response.
- [ ] bot hu response.
- [ ] no bot action after terminal settlement.

Phase 6a verification:

- `run_new_rule_tests.py`: all 10 scripts passed.
- `test_new_rule_gamestate.py`: 61 tests passed.
- `test_new_rule_get_action.py`: 4 tests passed.
- `test_new_rule_room_creation.py`: 38 tests passed.
- Windows logging rollover `PermissionError` noise still appears, but tests exit successfully.

## Phase 7: Room, Ready, Next-Hand, And Game-End Flow

Goal: line up room lifecycle with existing rules.

Guiding rule for this phase:

- Before changing `game_new_rule`, inspect the matching path in existing rules first.
- Use Qingque/Guobiao for standard Chinese-style round lifecycle, ready phase, game-end payload, record storage, and custom-room cleanup.
- Use Sichuan for blood-battle style "winner exits, remaining players continue" flow and visible tag/settlement timing.
- Do not invent a new public Unity protocol if an old-rule message shape can work.

Old-rule reuse review checklist:

- Reuse old-rule message shapes and UI paths where possible, but do not blindly inherit old-rule semantics.
- `action_tick`: keep stale-action protection for live hand actions (`cut`, `hu`, `pass`, `chi`, `peng`, `gang`), but do not reject result-panel `ready` just because Unity carries the previous ask tick.
- `ready` phase: only whole-hand endings enter ready/next-hand flow. Mid-hand blood-battle wins are not ready phases.
- `show_result`: use for whole-hand settlement. Mid-hand wins should remain weak notifications and must not reveal fan lists or score changes.
- `game_end`: reserve for the configured match ending after all `max_round * 4` hands, not for a single hand ending.
- Winner information visibility: do not reveal a mid-hand winner's full hand, concealed kong true tiles, fan list, or score changes before final settlement.
- Concealed kong: keep true concealed-kong tile hidden from non-owner viewers until final reveal, even if an old payload shape would make sending the real tile easy.
- Chi eligibility: use physical next seat after the discarder, not next active player. If that seat has already won and exited, no one may chi.
- Bot reuse: reuse old bot scheduling/delay and safe decision helpers, but submit through `game_new_rule.get_action`; do not route new-rule actions directly into old-rule action handlers.
- Record/replay: reuse record shapes, but review mid-hand winner exits, deferred final reveal, concealed-kong reveal timing, and score-change timing explicitly.
- Spectator: before enabling spectators, audit for information leaks from mid-hand fan lists, concealed kong true tiles, hidden hands, and deferred score changes.
- Score updates: internal deferred settlement is fine, but Unity/spectator/replay/public records should not present mid-hand score deltas as final public information.
- Room options: verify every option across Unity send, backend storage, and actual gameplay effect. Do not expose old-rule toggles as if functional when new rule ignores them.

Current confirmed mismatch:

- Existing rules send `game_start` before any first action prompt:
  - Guobiao: `init_guobiao_tiles()` -> `broadcast_game_start()` -> buhua/first `broadcast_ask_hand_action()`.
  - Qingque: `init_qingque_tiles()` -> `broadcast_game_start()` -> dealer `do_action/deal_tile` -> `broadcast_ask_hand_action()`.
  - Sichuan: `init_sichuan_tiles()` -> `broadcast_game_start()` -> dingque -> `broadcast_ask_hand_action()`.
- New rule has been fixed to emit `gamestate/new_rule/game_start` before the first `gamestate/new_rule/broadcast_hand_action`.
- Existing rules then continue through round result, ready phase, next-round `game_start`, final `game_end`, record storage, gamestate cleanup, and room finish/destroy.
- New rule now has a multi-round closeout after hand settlement: `show_result`, `ready_status`, next-round `game_start`, and final `game_end` after all configured hands, followed by gamestate cleanup and custom-room finish.
- New rule is still incomplete for final storage, replay validation, spectator incremental updates, and full Unity manual parity.

Current room-option wiring notes:

- Keep `game_round = 3` / west-round option supported. The new-rule room validator accepts 1 through 4, and the new-rule loop naturally runs `max_round * 4` hands.
- Unity new-rule create-room path currently sends real values for:
  - `game_round`
  - `password`
  - `random_seed` / "复式"
  - `tourist_limit`
- Backend new-rule room creation currently uses:
  - `password` via common `has_password` / `room_passwords` join validation.
  - `random_seed` via the shared random-seed system and records `is_player_set_random_seed`.
  - `tourist_limit` via common room-join rejection for tourist accounts.
  - `game_round` as `NewRuleGameState.max_round`.
- Unity currently forces new-rule `tips = false`, and new-rule gameplay has not wired the shared hand/tile tip system yet.
- Unity currently forces new-rule `allow_spectator = false`, and backend new-rule room creation also stores `allow_spectator: False`.
- Future room/UI work should either wire `tips` and `allow_spectator` properly for new rule, or hide/disable those toggles while new rule is selected so the create-room UI does not imply inactive features are available.

Tasks:

- [ ] Audit room creation route `room/create_NewRule_room`.
- [ ] Decide hidden/dev-only vs public UI state.
- [ ] Preserve and manually verify `game_round = 3` west-round rooms.
- [ ] Document or test create-room option behavior for password, random seed, tourist limit, tips, and spectator.
- [ ] Decide whether to implement new-rule tips or hide the tips toggle for new-rule rooms.
- [ ] Decide whether to implement delayed/realtime spectator support or hide the spectator toggle for new-rule rooms.
- [ ] Ensure host-only add-bot/start checks match existing rules.
- [x] Ensure `waiting_ready` behavior uses existing ready phase conventions.
  - Reference Guobiao/Qingque `run_hu_result_ready_phase`, `hu_result_ready_wait_seconds`, and `broadcast_ready_status`.
  - Reference Sichuan `_ready_phase` for blood-battle result timing.
  - Humans should receive `ready`; bots should be treated as already ready or auto-ready, matching old rules.
  - Unity should receive `gamestate/new_rule/ready_status` with `Ready_status_info`.
- [ ] Ensure fixed dealer rotation is implemented intentionally, not accidentally inherited from random seat switching.
- [x] Add multi-round loop behavior.
  - Compare with Guobiao/Qingque `while current_round <= max_round * 4`.
  - New rule should use fixed dealer rotation, not dealer repeat/renchan.
  - Each next round should reset round-only state, initialize tiles, send a new `game_start`, then start the first hand action.
- [x] Confirm all-round `game_end` behavior after configured hand count in backend tests.
  - Reference `broadcast_game_end` in Guobiao/Qingque/Sichuan.
  - New rule should emit `gamestate/new_rule/game_end` with `Game_end_info`/`player_final_data`.
  - Unity `NetworkManager.cs` already routes `gamestate/new_rule/game_end`, but `GameStateNetworkManager.cs` still needs the new-rule case in the `HandleGameEnd` branch.
- [x] Add `gamestate/new_rule/ready_status` Unity handling.
  - Unity `NetworkManager.cs` already routes it.
  - `GameStateNetworkManager.cs` now routes the new-rule case to `HandleReadyStatus`.
- [x] Add `gamestate/new_rule/game_end` Unity handling.
  - Unity `NetworkManager.cs` already routes it.
  - `GameStateNetworkManager.cs` now routes the new-rule case to `HandleGameEnd`.
- [x] Add multi-round `ready_status`, repeated `game_start`, final `game_end`, and cleanup path.
- [ ] After final `game_end`, validate existing cleanup paths in Unity manual playtest.
  - Reference Guobiao/Qingque/Sichuan tail flow:
    - `await self.game_server.gamestate_manager.cleanup_game_state_complete(gamestate_id=self.gamestate_id)`
    - match rooms: `destroy_room`
    - custom rooms: `finish_custom_game_room`
- [ ] Confirm disconnect/reconnect during:
  - self turn;
  - discard response;
  - post-chi/peng only-cut;
  - robbed-kong ask;
  - final settlement;
  - waiting ready.

Recommended implementation order for Phase 7:

1. [x] Add backend payload builders for `ready_status` and `game_end`, copying existing response shapes rather than creating new dictionaries from scratch.
2. [x] Add Unity `GameStateNetworkManager.cs` switch cases for `gamestate/new_rule/ready_status` and `gamestate/new_rule/game_end`.
3. [x] Add a minimal result-ready phase after new-rule final settlement.
4. [x] Add final `game_end` emission and cleanup for one configured game.
5. [x] Expand into multi-round loop with fixed dealer rotation and repeated `game_start`.
6. Add room-creation/integration tests proving message order:
   - first `game_start` before first `broadcast_hand_action`;
   - final `show_result` before `ready_status`;
   - final configured round sends `game_end`;
   - cleanup removes gamestate mappings and finishes/destroys the room.
7. Unity manual test:
   - create new-rule room;
   - start game;
   - play to wall exhaustion and to 3 winners;
   - confirm result panel, ready/continue behavior, next-round start, final game-end panel, and room return state.

## Phase 8: Test Strategy

Run tests in layers after each phase.

Layer A: Python calculation tests:

- `test_new_rule_scoring.py`
- `test_new_rule_service.py`
- `test_new_rule_tingpai.py`

Layer B: Python state/action tests:

- `test_new_rule_action_check.py`
- `test_new_rule_get_action.py`
- `test_new_rule_gamestate.py`
- `test_new_rule_boardcast.py`
- `test_new_rule_router.py`
- `test_new_rule_gamestate_manager.py`
- `test_new_rule_room_creation.py`

Layer C: Existing-rule smoke to guard against shared-interface regressions:

- Qingque create/start/discard with bots.
- Guobiao create/start/discard with bots.
- Sichuan create/start/blood-battle continuation with bots.

Layer D: Unity compile:

- Batchmode compile with Unity `6000.5.2f1`.

Layer E: Unity manual smoke:

- Original Qingque baseline.
- New-rule room start.
- New-rule discard.
- New-rule chi/cancel.
- New-rule hu continuation.
- New-rule wall exhaustion.
- New-rule 3-winner settlement.
- New-rule record/replay if storage is implemented.

## Phase 9: Commit Strategy

Use small commits rather than one giant refactor commit.

Suggested commit slices:

1. Audit docs only.
2. Canonical action-field rewrite and tests.
3. Status-name alignment and tests.
4. Broadcast/Unity payload convergence.
5. Record/storage alignment.
6. Bot scheduling/reuse.
7. Unity cleanup and docs.

Do not commit:

- local `secret_key.txt` changes;
- Unity batchmode logs;
- unrelated Unity editor churn unless required.

## Open Questions

- Should new rule continue using `gamestate/new_rule/...` message paths even if payloads match old Guobiao payloads?
- Resolved: `unity_game_info` has been removed; normal `game_info` is canonical for new rule.
- Should new-rule storage reuse an existing store function pattern or define `store_new_rule_game_record`?
- Should fan stats be stored immediately, or delayed until fan localization/replay is stable?
- For bot testing, should smart bots be allowed to hu aggressively, or should a passive/dev bot mode remain default for manual UI testing?
- How should final settlement display multiple winners: one aggregate panel or sequential winner panels?

## Immediate Next Steps

Completed:

- Created refactor branch from the saved snapshot route.
- Ran current Python new-rule tests to establish a baseline.
- Built the audit matrix.
- Completed Phase 2/3/4 public protocol alignment.
- Completed Phase 5a minimal record scaffold.
- Completed Phase 6a async bot adapter and removed synchronous fallback.

Next:

1. Run Unity manual parity check for new-rule multi-round play: result ready, next-hand `game_start`, fixed dealer rotation, and final `game_end`.
2. Continue Phase 5b: database storage, replay validation, spectator updates, and multi-round record lifecycle.
3. Continue Phase 6b: finer smart-bot/pass/hu tests and manual Unity checks with both bot buttons.
4. After record/bot parity, run Unity compile and a fresh manual new-rule playtest.

## 2026-07-05 Update: Unity Smoke Issues 2

Completed:

- Discard-claim ming-gang now carries the supplement draw through the returned window and broadcasts it as `deal_gang_tile`, matching existing Chinese-rule paths.
- Result-panel ready now follows old-rule timeout semantics: pending `ready` defaults to ready on timeout, and stale `action_tick` rejection still does not apply to `ready`.
- Final settlement now supports sequential multi-winner display by emitting one `show_result` / `settle_hu` step per deferred winner. Unity new rule reuses the existing Sichuan settle-hu queue for those steps.
- Unity `FanTextDictionary` now has `new_rule/standard` fan-id display names and point text, so final fan rows should no longer show `0` merely because the client lacks a mapping.
- Backend verification passed with `.\.venv\Scripts\python.exe run_new_rule_tests.py` (10 scripts).

Still needs manual Unity verification:

- Unity batchmode compile check passed after the Editor was closed.
- Verify discard-claim ming-gang, added kong, and concealed kong visually: meld area update, supplement tile, remaining tile count.
- Verify continue-button timeout starts the next hand.
- Verify final settlement fan values and three-winner sequential panels.
- Verify the Unity changes did not regress Qingque/Guobiao/Sichuan result handling, since new rule now reuses the Sichuan endgame queue branch.
