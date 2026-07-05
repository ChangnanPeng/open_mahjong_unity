# New Rule Legacy Alignment Audit

Last updated: 2026-07-05.

Scope: audit the current `new_rule` implementation against Qingque/Guobiao/Sichuan conventions before code refactor.

Baseline commit: `cface9e5`.

Current branch: `codex/new-rule-legacy-alignment`.

## Baseline Test Result

All current new-rule Python tests passed before refactor:

- `test_new_rule_scoring.py`: 34 tests passed.
- `test_new_rule_service.py`: 5 tests passed.
- `test_new_rule_tingpai.py`: 5 tests passed.
- `test_new_rule_action_check.py`: 9 tests passed.
- `test_new_rule_get_action.py`: 4 tests passed.
- `test_new_rule_boardcast.py`: 13 tests passed.
- `test_new_rule_gamestate.py`: 55 tests passed.
- `test_new_rule_router.py`: 3 tests passed.
- `test_new_rule_gamestate_manager.py`: 1 test passed.
- `test_new_rule_room_creation.py`: 38 tests passed.

Caveat:

- `test_new_rule_room_creation.py` emitted Windows logging rollover `PermissionError` noise for `logs/app.log`, but the command exited successfully. Treat this as test-environment noise unless it starts failing commands.

## Audit Matrix

| Area | Current new-rule shape | Existing-rule target | Decision | Phase |
| --- | --- | --- | --- | --- |
| Status after discard | `waiting_discard_response` | `waiting_action_after_cut` | Rename, no alias | Phase 3 |
| Status after chi/peng | `waiting_only_cut` | `onlycut_after_action` | Rename, no alias | Phase 3 |
| Status after added kong | `waiting_rob_kong` | `waiting_action_qianggang` | Rename, no alias | Phase 3 |
| Self turn status | `waiting_hand_action` | `waiting_hand_action` | Keep | Phase 3 |
| End status | `END` | `END` | Keep | Phase 3 |
| Cut action tile | `tile_id` | `TileId` | Rewrite canonical field, remove prototype field | Phase 2 |
| Cut action index | `cut_index` | `cutIndex` | Rewrite canonical field, remove prototype field | Phase 2 |
| Cut class | missing or inferred late | `cutClass` | Store canonical field in queued actions | Phase 2 |
| Response target | `target_tile` | `target_tile` | Keep | Phase 2 |
| `submit_action` API | keyword args use `tile_id`, `cut_index` | old-style `TileId`, `cutIndex`, `cutClass` | Rewrite API/tests | Phase 2 |
| `get_action.py` API | receives old fields but converts to prototype fields | keep old fields through queue | Rewrite conversion away | Phase 2 |
| Bot fallback action | returns prototype fields and runs synchronously | old-style async bot pipeline | Rewrite later; first remove prototype fields in fallback | Phase 2/6 |
| `boardcast.py` do-action cut index | reads `action_info["cut_index"]` | read canonical `cutIndex` or do-action already has `cut_tile_index` | Rewrite | Phase 2 |
| Unity route path | `gamestate/new_rule/...` | existing route style where possible | Keep for now; path separation may remain useful | Phase 4 |
| Unity `unity_game_info` | new bridge field | normal `game_info` should eventually be canonical | Audit/remove later | Phase 4 |
| Unity DTOs | uses existing `ask_*`, `do_action_info`, `show_result_info` plus bridge | existing DTOs without bridge-only fields | Converge later | Phase 4 |
| Record helpers | new rule mostly not using full `player_action_record_*` flow | shared `game_record_manager` helpers | Audit and align later | Phase 5 |
| Storage | no `store_new_rule_game_record` registered | `game_records` + `game_player_records` pattern | Add or reuse store later | Phase 5 |
| Bot pipeline | synchronous `_default_bot_action` | async `public.ai` scheduling | Replace later after status/action alignment | Phase 6 |

## Phase 2 Code Targets

First code change should be narrow and reviewable:

- `open_mahjong_server/server/gamestate/game_new_rule/NewRuleGameState.py`
- `open_mahjong_server/server/gamestate/game_new_rule/get_action.py`
- `open_mahjong_server/server/gamestate/game_new_rule/boardcast.py`
- tests under `open_mahjong_server/server/gamestate/game_new_rule/`

Phase 2 final state:

- [x] Queued actions use only `TileId`, `cutIndex`, `cutClass`, `target_tile`.
- [x] Production code does not read or write cut action `tile_id` or `cut_index`.
- [x] Tests assert canonical action fields only.
- Status names are not renamed yet, except if a local test fixture must be touched for action data.

Verification after Phase 2:

- `rg -n "tile_id|cut_index" open_mahjong_server\server\gamestate\game_new_rule` returns no matches.
- `test_new_rule_get_action.py`: passed.
- `test_new_rule_router.py`: passed.
- `test_new_rule_boardcast.py`: passed.
- `test_new_rule_gamestate.py`: 55 tests passed.
- `test_new_rule_action_check.py`: 9 tests passed.
- `test_new_rule_gamestate_manager.py`: 1 test passed.
- `test_new_rule_room_creation.py`: 38 tests passed.
- Windows logging rollover `PermissionError` noise still appears, but tests exit successfully.

## Phase 3 Code Targets

Second code change should rename statuses everywhere:

- `waiting_discard_response` -> `waiting_action_after_cut`
- `waiting_only_cut` -> `onlycut_after_action`
- `waiting_rob_kong` -> `waiting_action_qianggang`

Phase 3 final state:

- Production code does not contain prototype status strings.
- Tests do not contain prototype status strings.
- Bot/status integration is closer to existing rules, but async bot reuse can still wait for Phase 6.

## Deferred Areas

Do not mix these into Phase 2/3:

- Removing `unity_game_info`.
- Changing Unity C# route handling.
- Adding database storage.
- Reworking record/replay.
- Replacing bot scheduling.
- Fan localization.

These are important, but doing them after action/status cleanup keeps the refactor understandable.
