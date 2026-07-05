# New Rule Unity Parity Checklist

Last updated: 2026-07-05.

Goal: make the new rule feel like a first-class Unity rule, using Qingque/Guobiao/Sichuan as behavioral references.

This is not a rule-definition checklist. It tracks Unity-facing protocol, pacing, UI behavior, bot behavior, and playtest parity.

Protocol-alignment work is tracked in `other/new_rule_protocol_alignment_plan.md`. Treat that file as the source of truth for making `game_new_rule` use old-style status names and action fields where possible.

## Current Status

Playable smoke status:

- New-rule hidden/dev room can be created from Unity.
- New-rule room can start with bots.
- Table renders.
- Discard works.
- Chi popup can appear.
- Chi now performs a visible meld.
- Canceling a response prompt no longer freezes the hand.
- Final settlement payload now includes Unity `show_result_info`.
- Remaining tile count now syncs from `unity_game_info.tile_count`.

Still under active verification:

- Wall exhaustion should show a draw/round-end settlement panel.
- Three winners should show final settlement.
- Mid-hand hu should hide fan details until final settlement.
- New-rule result panel display is functional but not yet polished.
- Bot behavior currently uses a temporary fallback, not the original bot task pipeline.

## Parity Reference

Use existing Qingque as the primary UX reference for:

- login -> room -> add bots -> start game flow
- bot action pacing
- action prompt timing
- discard animation
- draw animation
- chi/peng/gang animation
- round result panel
- returning from result panel
- score history updates

Use Sichuan as a secondary reference for:

- blood-battle continuation after one player wins
- winner exits while the hand continues
- deferred/final settlement behavior

Use Guobiao/Classical as references for:

- honors/no-flowers style hands
- normal chi/peng/gang display
- final single-hand settlement display

## Phase A: Protocol And Routing

Status: partially complete.

- [x] `NetworkManager.cs` routes `gamestate/new_rule/...` to game-state handling.
- [x] `GameStateNetworkManager.cs` handles new-rule start/ask/do/result/reconnect paths.
- [x] Unity sends `gamestate/new_rule/cut_tile` when `roomRule == "new_rule"`.
- [x] Unity sends `gamestate/new_rule/send_action` when `roomRule == "new_rule"`.
- [x] Backend emits `unity_game_info`.
- [x] Backend emits `ask_hand_action_info`.
- [x] Backend emits `ask_other_action_info`.
- [x] Backend emits `do_action_info`.
- [x] Backend final settlement emits `show_result_info`.
- [ ] Confirm `gamestate/new_rule/game_end` behavior after all configured rounds.
- [ ] Confirm reconnect during active hand.
- [ ] Confirm reconnect after final settlement.
- [ ] Confirm ready/next-hand flow after result panel.
- [ ] Align new-rule public statuses/action fields with Qingque/Guobiao/Sichuan conventions. See `other/new_rule_protocol_alignment_plan.md`.

## Phase B: Table State And Visible Actions

Status: partially complete.

- [x] Initial hand render.
- [x] Other players' hands hidden.
- [x] Self draw tile visible only to self.
- [x] Other players' draw tile hidden.
- [x] Discard visible action.
- [x] Chi visible action with `combination_mask`.
- [x] Peng visible action with `combination_mask` in tests.
- [x] Ming-gang visible action with `combination_mask` in tests.
- [x] Remaining tile count syncs from server.
- [ ] Verify peng in Unity.
- [ ] Verify ming-gang in Unity.
- [ ] Verify concealed kong in Unity.
- [ ] Verify concealed kong hides true tile from non-owner viewers.
- [ ] Verify added kong in Unity.
- [ ] Verify robbing kong in Unity.
- [ ] Verify winner exits while remaining players continue.
- [ ] Verify current-player marker does not point to exited winners.
- [ ] Verify discards remain consistent after chi/peng/gang removes a river tile.
- [ ] Verify final reveal restores concealed kong true tiles.

## Phase C: Action Prompts

Status: partially complete.

- [x] Self turn `cut` prompt works.
- [x] `chi/pass` prompt appears.
- [x] Cancel/pass after response prompt works.
- [ ] Verify `peng/pass` prompt.
- [ ] Verify `gang/pass` prompt.
- [ ] Verify `hu/pass` discard-win prompt.
- [ ] Verify multi-ron prompt behavior.
- [ ] Verify `hu_self` prompt.
- [ ] Verify `angang` prompt.
- [ ] Verify `jiagang` prompt.
- [ ] Verify rob-kong `hu/pass` prompt.
- [ ] Verify same-tile discard-win lockout hides/blocks illegal hu in Unity.
- [ ] Verify post-chi/peng only-cut state does not allow immediate kong.
- [ ] Verify action tick prevents stale delayed button clicks.

## Phase D: Settlement And Score Display

Status: first bridge implemented; needs Unity verification.

- [x] Backend final settlement applies deferred score changes once.
- [x] Backend final settlement includes final scores.
- [x] Backend final settlement includes total `score_changes`.
- [x] Backend wall-exhaustion settlement uses `hu_class = "liuju"`.
- [ ] Verify wall exhaustion displays a result panel.
- [ ] Verify 3 winners displays a final result panel.
- [ ] Verify final scores match backend score changes.
- [ ] Verify 0-point win displays without crashing.
- [ ] Verify mid-hand hu does not show fan list or score changes.
- [ ] Verify final settlement reveals deferred fan list and score changes.
- [ ] Decide whether final settlement should show one aggregate panel or one panel per winner.
- [ ] Add new-rule fan-name localization for Unity display.
- [ ] Verify score history panel updates.
- [ ] Verify next-hand ready flow.
- [ ] Verify all-round game-end panel after configured round count.

## Phase E: Bot Parity

Status: temporary fallback exists; original bots not yet wired into new rule.

Current new-rule temporary bot:

- Implemented inside `NewRuleGameState._default_bot_action`.
- If `pass` is legal, it passes.
- Else if `cut` is legal, it discards the first hand tile.
- It acts synchronously inside `wait_action`, so multiple bots can appear to act instantly.
- It does not use original `auto_cut_ai.py` or `smart_bot_ai.py`.

Existing original bots:

- `user_id == 0`: auto-cut bot, "moqie Robert".
- `user_id == 2`: smart bot, "paixiao Robert".
- Their decision logic lives in:
  - `server/gamestate/public/ai/auto_cut_ai.py`
  - `server/gamestate/public/ai/smart_bot_ai.py`
  - `server/gamestate/public/ai/smart_bot_logic.py`
- Existing rule boardcast modules schedule those bots through `asyncio.create_task(...)`.
- The existing bot task path includes a built-in `_BOT_DELAY = 0.5`.

Ease of reuse:

- Auto-cut bot is easy to reuse.
- Smart bot decision logic is moderately easy to reuse for discard choice.
- Smart bot full action behavior is not safe to directly reuse without an adapter.

Why direct import is not enough:

- Existing `auto_cut_ai.py` and `smart_bot_ai.py` import `server.gamestate.public.ai.get_action`.
- That public `get_action` writes old-style action dictionaries:
  - `TileId`
  - `cutClass`
  - `cutIndex`
- New-rule live loop expects its own action format:
  - `tile_id`
  - `target_tile`
  - `cut_index`
- Existing bots use old game statuses:
  - `waiting_action_after_cut`
  - `onlycut_after_action`
  - `waiting_action_qianggang`
  - `waiting_buhua_round`
- New rule uses:
  - `waiting_hand_action`
  - `waiting_only_cut`
  - `waiting_discard_response`
  - `waiting_rob_kong`
- Existing smart bot assumes flowers may exist and can choose `buhua`; new rule has no flowers.
- Existing smart bot can choose hu immediately whenever legal; for new-rule testing this is acceptable only if we want bots to self-play, but it may shorten manual test scenarios.
- Existing smart bot scoring is shanten/acceptance based, not new-rule fan-aware. This is fine for a "reasonable bot", not a competitive bot.

Protocol-alignment decision:

- Prefer changing new-rule public statuses/action fields to match existing rules before building a large bot-specific translation layer.
- Keep rule-specific logic in `game_new_rule`, but expose old-style status names and cut fields wherever Unity/bots already have expectations.
- Detailed migration steps live in `other/new_rule_protocol_alignment_plan.md`.

Recommended bot integration plan:

1. Complete the protocol-alignment plan enough that new-rule can accept/emit old-style statuses and action dictionaries.
2. Add a new-rule bot adapter module if direct reuse is still not clean enough, for example:
   - `server/gamestate/game_new_rule/bot_adapter.py`
3. Do not import `public.ai.auto_cut_ai.auto_cut_action` blindly until status/action compatibility is verified.
4. Reuse lower-level decision helpers where safe:
   - `has_draw_slot`
   - `infer_bot_cut_class`
   - `smart_bot_logic.count_melds`
   - `smart_bot_logic.count_visible_tiles`
   - `smart_bot_logic.find_best_cut`
   - `smart_bot_logic.find_best_cut_score`
   - `smart_bot_logic.should_accept_hu`
5. Implement new-rule-native bot submission through:
   - `server.gamestate.game_new_rule.get_action.get_ai_action`
   - or directly `game_state.submit_action(...)`
6. Map statuses only if protocol alignment is incomplete:
   - `waiting_hand_action`: use hand-action bot logic.
   - `waiting_only_cut`: cut after chi/peng.
   - `waiting_discard_response`: hu/peng/gang/chi/pass decision.
   - `waiting_rob_kong`: hu/pass decision.
7. Schedule bot actions asynchronously instead of resolving them synchronously inside `wait_action`.
8. Keep the existing `_BOT_DELAY = 0.5` behavior.
9. Add tests for:
   - auto-cut bot delay path queues cut.
   - smart bot cut path queues legal cut.
   - bot pass after discard response.
   - bot chi/peng/gang response can be queued.
   - bot hu response can be queued.
   - bot action after END is ignored.

Minimum useful bot upgrade:

- Replace synchronous `_default_bot_action` with async scheduled new-rule bot tasks.
- For `user_id == 0`, implement auto-cut/pass only.
- For `user_id == 2`, reuse smart cut selection, but initially keep discard-response choices conservative:
  - accept legal hu if allowed.
  - otherwise pass.
  - add chi/peng/gang smart decisions later.

Risk:

- If bots can hu/claim too aggressively, manual Unity testing becomes harder.
- Keep a dev setting or bot mode that uses passive bots for UI debugging.

## Phase F: Room And UI Polish

Status: dev-only.

- [x] Dev-only `新规则测试` room creation exists.
- [ ] Replace temporary/dev room creation with official room config entry.
- [ ] Add display strings for new rule and sub-rule.
- [ ] Decide public room-list visibility.
- [ ] Add new-rule option to normal room filters.
- [ ] Add rule help / short description.
- [ ] Add spectator support decision.

## Phase G: Regression Against Existing Rules

Run after each broad Unity routing change:

- [ ] Qingque tourist room with 3 bots: start, discard, round end.
- [ ] Guobiao tourist room with 3 bots: start, discard, round end.
- [ ] Sichuan tourist room with 3 bots: start, blood-battle continuation, round end.
- [ ] Classical tourist room with 3 bots.
- [ ] Riichi tourist room with 3 bots.

## Immediate Next Recommendations

1. Re-test Issue 4 in Unity:
   - wall exhaustion should show settlement.
   - remaining tile count should reach 0.
2. Add new-rule bot adapter for `user_id == 0` first.
3. Once auto-cut bot is stable, add smart bot discard selection for `user_id == 2`.
4. Keep the passive fallback mode available for deterministic UI testing.
