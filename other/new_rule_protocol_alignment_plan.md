# New Rule Protocol Alignment Plan

Last updated: 2026-07-05.

Goal: make `game_new_rule` speak the same game-state/status/action protocol shape as the existing Qingque/Guobiao/Sichuan rules wherever possible, while keeping the new rule's actual game logic independent.

Current work snapshot: `other/new_rule_work_snapshot_2026-07-05.md`.

Broader refactor plan: `other/new_rule_legacy_alignment_refactor_plan.md`.

This plan exists because Unity and the original bot pipeline are not pure render/AI layers. They depend on established backend state names, action dictionaries, and broadcast payload fields. The more `new_rule` matches those conventions, the less special-case bridge code is needed.

## Current Situation

The new rule is playable enough for Unity smoke testing:

- Unity can create a hidden/dev `new_rule` room.
- The room can start with bots.
- The table renders.
- Discard works.
- Chi/cancel no longer freezes the game.
- Chi can render visibly with `combination_mask`.
- Final settlement now includes Unity-compatible `show_result_info`.
- Remaining tile count syncs from `unity_game_info.tile_count`.

Several issues came from protocol mismatch rather than rule logic:

- Unity needed explicit routing for `gamestate/new_rule/...`.
- Unity expected visible action fields such as `combination_mask`, `show_result_info`, and remain-tile data.
- Temporary new-rule bots act synchronously and do not use the original bot pipeline.
- New-rule internal states do not match the old status names used by existing bots and boardcast code.

## Existing Protocol Baseline

Qingque, Guobiao, Classical, and Sichuan mostly share these old-style game statuses:

- `waiting_hand_action`
- `waiting_action_after_cut`
- `onlycut_after_action`
- `waiting_action_qianggang`
- `deal_card`
- `deal_card_after_gang`
- `waiting_ready`
- `END`

Sichuan adds rule-specific extensions such as:

- `waiting_dingque`
- `settle_win`

Old-style cut action data uses:

```python
{
    "action_type": "cut",
    "cutClass": False,
    "TileId": 12,
    "cutIndex": 0,
}
```

Old-style response action data uses:

```python
{
    "action_type": "peng",
    "target_tile": 12,
}
```

Existing bot code is built around this shape:

- `open_mahjong_server/server/gamestate/public/ai/auto_cut_ai.py`
- `open_mahjong_server/server/gamestate/public/ai/smart_bot_ai.py`
- `open_mahjong_server/server/gamestate/public/ai/get_action.py`

Qingque and Guobiao both use the shared `public.ai.smart_bot_ai` path, so the original smart bot is not Qingque-specific.

## Current New-Rule Differences

New-rule currently uses these custom statuses:

- `waiting_hand_action`
- `waiting_only_cut`
- `waiting_discard_response`
- `waiting_rob_kong`
- `END`

New-rule internal queued action data currently uses snake-case fields:

```python
{
    "action_type": "cut",
    "tile_id": 12,
    "cut_index": 0,
}
```

The public new-rule router already accepts old-style Unity fields such as `TileId`, `cutIndex`, and `cutClass`, but the live-loop internals and tests still lean on custom status/action names.

## Target Direction

Prefer old-style public protocol names at the boundary used by Unity, routers, boardcast helpers, and bots.

Target status mapping:

| Current new-rule status | Target public/canonical status |
| --- | --- |
| `waiting_hand_action` | `waiting_hand_action` |
| `waiting_discard_response` | `waiting_action_after_cut` |
| `waiting_only_cut` | `onlycut_after_action` |
| `waiting_rob_kong` | `waiting_action_qianggang` |
| `END` | `END` |

Target action field mapping:

| Current internal field | Target public/canonical field |
| --- | --- |
| `tile_id` | `TileId` |
| `cut_index` | `cutIndex` |
| inferred cut class | `cutClass` |
| `target_tile` | `target_tile` |

Clean refactor rule:

- The review-quality final code should use only the existing-rule canonical field names.
- Do not keep long-term aliases for the earlier prototype names.
- Do not keep tests that assert both prototype and canonical shapes.
- Temporary migration scaffolding is acceptable only while moving a small area, and should be removed before the phase is considered complete.

## Non-Goals

Do not make the new rule a copy of Qingque, Guobiao, or Sichuan rule logic.

Do not change these new-rule decisions:

- 136-tile wall, honors included, no flowers.
- No dead wall.
- No dingque.
- No chajiao.
- No immediate kong scoring.
- No cuohe/false-win flow.
- 0-point legal wins are allowed.
- Blood-battle continuation after a player wins.
- End hand at 3 winners or wall exhaustion.
- Fixed dealer rotation.
- Chi only by physical next seat, not next active player.
- After chi/peng, player must discard before concealed/added kong.
- Same-tile discard-win lockout, including robbed-kong hu.
- Concealed kong tile hidden from other players until final reveal.
- Mid-hand hu does not reveal fan details; fan details are revealed at final settlement.

## Phase 1: Document And Freeze The Boundary

Status: current phase.

Tasks:

- [x] Record this protocol-alignment plan.
- [x] Link this plan from the Unity playtest plan.
- [x] Link this plan from the Unity parity checklist.
- [ ] Identify all new-rule code paths that read or write `game_status`.
- [ ] Identify all new-rule code paths that read or write queued action dictionaries.
- [ ] Add a small protocol/constants helper API before broad renames, if it makes the final canonical code clearer.

Suggested helper names:

- `get_cut_tile(action_data)`
- `get_cut_index(action_data)`
- `set_cut_fields(action_data, tile_id, cut_index, cut_class)`

## Phase 2: Canonical Action Data Rewrite

Goal: rewrite new-rule code to use the existing-rule action field style as the only production shape.

Tasks:

- [ ] Update `NewRuleGameState.submit_action(...)` to store canonical action fields.
- [ ] Keep `get_action.py` submitting `TileId`, `cutIndex`, `cutClass`.
- [ ] Make queued cut actions use only:
  - `TileId`
  - `cutIndex`
  - `cutClass`
- [ ] Remove prototype cut fields from production code:
  - `tile_id`
  - `cut_index`
- [ ] Update `boardcast.py` to read canonical fields directly.
- [ ] Add tests proving the canonical field style works.

Success check:

- Existing new-rule Python tests still pass.
- Unity can still discard, chi, cancel, and reach final settlement.

## Phase 3: Status Name Alignment

Goal: expose old-style status names to bot/Unity-facing logic.

Tasks:

- [ ] Replace public use of `waiting_discard_response` with `waiting_action_after_cut`.
- [ ] Replace public use of `waiting_only_cut` with `onlycut_after_action`.
- [ ] Replace public use of `waiting_rob_kong` with `waiting_action_qianggang`.
- [ ] Update `game_new_rule/get_action.py`.
- [ ] Update `game_new_rule/boardcast.py`.
- [ ] Update `game_new_rule/test_new_rule_*` expected statuses.
- [ ] Remove prototype status aliases from production code and tests.
- [ ] Update docs after code settles.

Success check:

- Status names in `game_new_rule` are close enough to old rules that bot adapters no longer need a custom status translation table for the main live-loop states.

## Phase 4: Bot Pipeline Reuse

Goal: replace temporary synchronous fallback bots with old-style async bot scheduling.

Temporary bot today:

- Lives in `NewRuleGameState._default_bot_action`.
- Passes when pass is legal.
- Otherwise discards the first hand tile.
- Runs synchronously, so multiple bot turns can appear instant in Unity.

Preferred migration:

- [ ] Keep a passive/debug bot mode available for manual UI testing.
- [ ] Add new-rule bot adapter or hook.
- [ ] Reuse `public.ai.auto_cut_ai` behavior for `user_id == 0` if status/action alignment is sufficient.
- [ ] Reuse safe smart-bot decision helpers for `user_id == 2`:
  - `count_melds`
  - `count_visible_tiles`
  - `find_best_cut`
  - `find_best_cut_score`
  - `should_accept_hu`
- [ ] Schedule bot actions asynchronously with the same approximate delay as existing rules.
- [ ] Ensure bots submit through new-rule validation, not by mutating state directly.

Initial bot behavior target:

- Auto-cut bot: cut/pass only.
- Smart bot: smart discard selection; accept legal hu if configured; otherwise conservative pass on response prompts.
- Chi/peng/gang smart decisions can come later.

## Phase 5: Unity Parity Regression

Run after protocol and bot changes:

- [ ] Original Qingque room with 3 bots: start, discard, hu/settlement.
- [ ] New-rule room with 3 bots: start, discard, chi/cancel, final settlement.
- [ ] New-rule wall exhaustion: result panel appears.
- [ ] New-rule 3 winners: result panel appears.
- [ ] New-rule mid-hand hu: no fan list until final settlement.
- [ ] New-rule 0-point hu: no crash, player exits, score change is 0.
- [ ] New-rule concealed kong: hidden from other players.
- [ ] New-rule physical-next-seat chi: if next seat has exited, nobody may chi.
- [ ] New-rule same-tile discard-win lockout: illegal hu prompt is hidden/blocked.

## Risk Notes

- A broad status rename can break many tests at once; do canonical action-field rewrite first.
- Unity may still need some `gamestate/new_rule/...` routing because room rules are separated by path, even if payloads are old-style.
- The smart bot may make manual testing harder if it wins too aggressively; keep a passive/dev bot path.
- New rule intentionally added stricter `action_tick` stale-action protection than the older `get_action.py` paths. This is useful for live hand actions such as `cut`, `hu`, `pass`, `chi`, `peng`, and `gang`, because delayed Unity button clicks should not be consumed after the server has advanced to a new ask window.
- Do not apply the stale `action_tick` rejection blindly to `ready`. Unity's result-panel continue button sends `SendAction("ready", 0)` with `LastAskActionTick`, which belongs to the previous hand-action/response ask. Existing rules accept `ready` based on `waiting_ready`, `waiting_players_list`, and `action_dict`; new rule should match that behavior and accept `ready` even when the carried `action_tick` is stale.
- For timeout behavior, old rules treat result-panel ready as confirmed after the display/ready deadline. New rule should likewise synthesize `ready` for pending ready players on timeout rather than leaving the next hand blocked.
- For discard-claim ming-gang, keep both layers aligned with old rules: the claim action must emit the meld update, and the supplement draw must be visible as `deal_gang_tile`. Do not expose it as ordinary `deal_tile`; Unity uses the action kind to choose the correct hand/animation path.
- For blood-battle final settlement, use the Sichuan-style sequential `show_result` steps when multiple deferred winners exist. Each deferred settlement gets one `liuju_step = "settle_hu"` payload, with `liuju_status_final` only on the last one.
- Do not leave prototype aliases in review-quality code.

## Immediate Next Steps

1. Add protocol/constants helpers only if they make the final canonical code clearer.
2. Migrate queued action data to old-style cut fields and remove prototype aliases.
3. Migrate status names to old-style names at public boundaries.
4. Re-run new-rule backend tests.
5. Re-run Unity smoke.
6. Then wire async bot scheduling.
