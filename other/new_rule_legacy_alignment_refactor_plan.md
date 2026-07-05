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

- New rule currently relies on `unity_game_info` bridge payloads.
- Unity has explicit `gamestate/new_rule/...` cases.
- Some bridge code was added because payloads were not originally shaped like old `GameInfo`, `AskHandActionGBInfo`, `AskOtherActionGBInfo`, `DoActionInfo`, and `ShowResultInfo`.

Bot:

- Current new-rule bots use synchronous fallback `_default_bot_action`.
- Existing bots expect old statuses and old cut fields.
- Qingque and Guobiao share the existing smart bot path; new rule should get closer to that path before writing a large adapter.

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
- `gamestate/new_rule/reconnect` is temporary until reconnect can send normal `game_start` plus pending ask just like existing rules.

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
- [ ] Remove Unity bridge branches that become redundant after payload convergence.

Phase 4 implementation slices:

- Phase 4a: backend payload type/field convergence. Status: complete in commit-in-progress for public message types.
- Phase 4b: Unity C# bridge cleanup (`unity_game_info`, `ask_action`, `final_settlement` paths).
- Phase 4c: reconnect behavior convergence.

Phase 4a verification:

- `rg -n "gamestate/new_rule/ask_action|gamestate/new_rule/final_settlement" open_mahjong_server\server\gamestate\game_new_rule open_mahjong_unity\Assets\Scripts\Network` returns no matches.
- `test_new_rule_boardcast.py`: 13 tests passed.
- `test_new_rule_gamestate.py`: 55 tests passed.
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

- [ ] Confirm `init_game_record(self)` is used and `game_title` includes:
  - `rule`
  - `sub_rule`
  - `max_round`
  - `start_time`
  - `room_type`
  - `match_type`
  - `hepai_limit`
  - new-rule-specific flags only if needed.
- [ ] Confirm each hand calls `init_game_round(self)`.
- [ ] Use existing `player_action_record_deal`.
- [ ] Use existing `player_action_record_cut`.
- [ ] Use existing `player_action_record_angang`.
- [ ] Use existing `player_action_record_jiagang`.
- [ ] Use existing `player_action_record_chipenggang`.
- [ ] Use existing `player_action_record_hu` where compatible.
- [ ] Add narrowly scoped new-rule record helpers only for truly new concepts:
  - mid-hand winner exits;
  - deferred final settlement reveal;
  - same-tile lockout should probably not appear as a replay action unless useful for debugging.
- [ ] Use `player_action_record_liuju` for wall exhaustion if compatible.
- [ ] Use `player_action_record_round_end`.
- [ ] Use `end_game_record`.
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

- [ ] Decide whether direct import of `public.ai.auto_cut_ai.auto_cut_action` is safe after alignment.
- [ ] If not direct, add a very thin new-rule bot adapter.
- [ ] Preserve old bot delay behavior.
- [ ] For `user_id == 0`, implement auto-cut/pass behavior first.
- [ ] For `user_id == 2`, reuse smart discard selection helpers:
  - `count_melds`
  - `count_visible_tiles`
  - `find_best_cut`
  - `find_best_cut_score`
  - `should_accept_hu`
- [ ] Keep response choices conservative initially:
  - accept legal hu if configured;
  - otherwise pass;
  - add chi/peng/gang decisions later.
- [ ] Make bot submissions go through new-rule validation.
- [ ] Ensure bot action after `END` is ignored.

Tests:

- [ ] auto-cut bot queues a delayed cut.
- [ ] smart bot queues a legal cut.
- [ ] bot pass after discard response.
- [ ] bot hu response.
- [ ] no bot action after terminal settlement.

## Phase 7: Room, Ready, Next-Hand, And Game-End Flow

Goal: line up room lifecycle with existing rules.

Tasks:

- [ ] Audit room creation route `room/create_NewRule_room`.
- [ ] Decide hidden/dev-only vs public UI state.
- [ ] Ensure host-only add-bot/start checks match existing rules.
- [ ] Ensure `waiting_ready` behavior uses existing ready phase conventions.
- [ ] Ensure fixed dealer rotation is implemented intentionally, not accidentally inherited from random seat switching.
- [ ] Confirm all-round `game_end` behavior after configured hand count.
- [ ] Confirm disconnect/reconnect during:
  - self turn;
  - discard response;
  - post-chi/peng only-cut;
  - robbed-kong ask;
  - final settlement;
  - waiting ready.

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
- Should `unity_game_info` be removed once normal `game_info` is canonical for new rule?
- Should new-rule storage reuse an existing store function pattern or define `store_new_rule_game_record`?
- Should fan stats be stored immediately, or delayed until fan localization/replay is stable?
- For bot testing, should smart bots be allowed to hu aggressively, or should a passive/dev bot mode remain default for manual UI testing?
- How should final settlement display multiple winners: one aggregate panel or sequential winner panels?

## Immediate Next Steps

1. Create a new refactor branch from the snapshot commit.
2. Run current Python new-rule tests to establish a baseline.
3. Build the audit matrix.
4. Implement canonical action-field rewrite first.
5. Then perform status-name alignment.
6. Only after those pass, continue to Unity payload cleanup and bot reuse.
