# New Rule Unity Parity Checklist

Last updated: 2026-07-06.

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
- Remaining tile count now syncs from `game_info.tile_count`.
- Bot path now uses the async `game_new_rule/bot.py` adapter; Unity pacing still needs manual verification.
- Other-player mid-hand self-draw now moves a hidden tile into the win/exposed area without revealing the real tile.

Still under active verification:

- Wall exhaustion should show a draw/round-end settlement panel.
- Three winners should show final settlement.
- Mid-hand hu should hide fan details until final settlement.
- New-rule result panel display is functional but not yet polished.
- Ready/next-round/game-end lifecycle still needs old-rule parity work.

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
- [x] Backend no longer emits prototype `unity_game_info`; new-rule payloads use old-style `game_info`.
- [x] Backend emits `ask_hand_action_info`.
- [x] Backend emits `ask_other_action_info`.
- [x] Backend emits `do_action_info`.
- [x] Backend final settlement emits `show_result_info`.
- [x] Backend emits `gamestate/new_rule/game_start` before the first `gamestate/new_rule/broadcast_hand_action`.
- [x] `GameStateNetworkManager.cs` handles `gamestate/new_rule/game_end` in the existing game-end branch.
- [x] `GameStateNetworkManager.cs` handles `gamestate/new_rule/ready_status` in the existing ready-status branch.
- [x] Backend emits `gamestate/new_rule/game_end` after all configured rounds.
- [ ] Confirm `gamestate/new_rule/game_end` behavior in Unity manual playtest.
- [ ] Confirm multi-round `gamestate/new_rule/game_end` behavior after all configured rounds in Unity manual playtest.
- [ ] Confirm reconnect during active hand.
- [ ] Confirm reconnect after final settlement.
- [ ] Confirm ready/next-hand flow after result panel.
- [ ] Align new-rule public statuses/action fields with Qingque/Guobiao/Sichuan conventions. See `other/new_rule_protocol_alignment_plan.md`.

Reference-before-edit reminder:

- For start flow, compare Guobiao/Qingque/Sichuan `game_loop_*` around `broadcast_game_start`.
- For ready flow, compare Guobiao/Qingque result-ready handling and Sichuan `_ready_phase`.
- For final game-end and cleanup, compare `broadcast_game_end`, `cleanup_game_state_complete`, and custom-room finish/destroy calls in existing rules.

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
- [x] Verify/fix other-player mid-hand self-draw presentation: the hidden drawn tile moves to the win/exposed area, and later continuation messages do not interrupt the animation.
- [ ] Verify current-player marker does not point to exited winners.
- [ ] Verify discards remain consistent after chi/peng/gang removes a river tile.
- [ ] Verify final reveal restores concealed kong true tiles.

Old-rule reuse review targets:

- [ ] Confirm mid-hand winners do not trigger result-ready flow.
- [ ] Confirm single-hand settlement uses `show_result`, while configured-match end uses `game_end`.
- [ ] Confirm mid-hand winner hand/fan/score information stays hidden until final settlement.
- [ ] Confirm concealed-kong true tiles are not exposed to non-owner viewers before final reveal.
- [ ] Confirm chi remains physical-next-seat only and does not skip to the next active player.
- [ ] Confirm new-rule bot actions use the new-rule adapter/validator, not old-rule action handlers.
- [ ] Confirm replay/record does not reveal deferred settlement data earlier than live play.
- [ ] Confirm spectator support stays disabled until information-leak cases are audited.
- [ ] Confirm room options shown for new rule are actually wired through Unity send, backend storage, and gameplay behavior.

## Phase C: Action Prompts

Status: partially complete.

- [x] Self turn `cut` prompt works.
- [x] `chi/pass` prompt appears.
- [x] Cancel/pass after response prompt works.
- [ ] Verify `peng/pass` prompt.
- [ ] Verify `gang/pass` prompt.
- [ ] Verify `hu/pass` discard-win prompt.
- [ ] Verify multi-ron prompt behavior: eligible players receive simultaneous `hu/pass` windows, click timing does not change accepted-winner order, and continuation draws from after the last fixed-seat-sorted accepted winner.
- [ ] Verify `hu_self` prompt.
- [ ] Verify `angang` prompt.
- [ ] Verify `jiagang` prompt.
- [ ] Verify rob-kong `hu/pass` prompt.
- [ ] Verify same-tile discard-win lockout hides/blocks illegal hu in Unity.
- [ ] Verify post-chi/peng only-cut state does not allow immediate kong.
- [ ] Verify action tick prevents stale delayed button clicks.
- [x] Verify/guard that new-rule cut requests carry `action_tick`; otherwise delayed cut submissions can bypass stale-action protection.
- [x] Verify/guard that result-panel `ready` is not rejected by stale previous ask `action_tick`; new rule has stricter stale-action protection than old rules, but `ready` must follow old-rule ready semantics.

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
- [x] Verify/fix final settlement sends stable fan ids to Unity so fan values are not displayed as 0 when settlements also contain Chinese fan names.
- [ ] Verify final settlement reveals deferred fan list and score changes in Unity.
- [x] Decide whether final settlement should show one aggregate panel or one panel per winner: show one panel per winner, in settlement order.
- [x] Add new-rule fan-id localization for Unity display.
- [ ] Verify new-rule multi-winner settlement queue in Unity manual playtest.
- [ ] Verify score history panel updates.
- [ ] Verify next-hand ready flow.
- [ ] Verify all-round game-end panel after configured round count.

Known next critical gap:

- Existing rules do not stop immediately after `show_result`; they enter a ready/confirmation phase and then either start the next round or send `game_end`.
- New rule now has a multi-round lifecycle:
  - `show_result`
  - `ready_status` between non-final rounds
  - next-round `game_start`
  - final `game_end` after `max_round * 4` hands
  - backend cleanup/room finish.
- Still pending: Unity manual verification of result-panel ready, next-round restart, and final game-end presentation.

## Phase E: Bot Parity

Status: async new-rule bot adapter exists; Unity pacing still needs manual verification.

Current new-rule bot:

- Implemented in `server/gamestate/game_new_rule/bot.py`.
- Scheduled asynchronously from `NewRuleGameState.wait_action()`.
- Uses new-rule validation through `game_new_rule.get_action`.
- Auto-cut style bots pass/cut with old-style delay.
- Smart bot (`user_id == 2`) reuses shared smart-bot evaluation helpers, then submits through the new-rule action path.
- Pending bot tasks are cancelled during cleanup.
- Stale action ticks and actions after `END` are ignored.

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

Why direct import is still not the preferred entry point:

- Existing `auto_cut_ai.py` and `smart_bot_ai.py` import `server.gamestate.public.ai.get_action`.
- That shared `public.ai.get_action` submits through old-rule action handlers, not `game_new_rule.get_action`.
- New rule now intentionally uses old-style public action fields:
  - `TileId`
  - `cutClass`
  - `cutIndex`
  - `target_tile`
- New rule now intentionally uses old-style statuses where possible:
  - `waiting_action_after_cut`
  - `onlycut_after_action`
  - `waiting_action_qianggang`
  - `waiting_hand_action`
- Existing smart bot assumes flowers may exist and can choose `buhua`; new rule has no flowers.
- Existing smart bot can choose hu immediately whenever legal; for new-rule testing this is acceptable only if we want bots to self-play, but it may shorten manual test scenarios.
- Existing smart bot scoring is shanten/acceptance based, not new-rule fan-aware. This is fine for a "reasonable bot", not a competitive bot.

Protocol-alignment decision:

- Prefer changing new-rule public statuses/action fields to match existing rules before building a large bot-specific translation layer.
- Keep rule-specific logic in `game_new_rule`, but expose old-style status names and cut fields wherever Unity/bots already have expectations.
- Detailed migration steps live in `other/new_rule_protocol_alignment_plan.md`.

Recommended bot integration plan:

1. Keep protocol/status/action fields aligned with old rules so bot code stays thin.
2. Keep the thin new-rule adapter instead of directly importing `public.ai.get_action`; that shared entry point submits old-rule handlers.
3. Reuse lower-level decision helpers where safe:
   - `has_draw_slot`
   - `infer_bot_cut_class`
   - `smart_bot_logic.count_melds`
   - `smart_bot_logic.count_visible_tiles`
   - `smart_bot_logic.find_best_cut`
   - `smart_bot_logic.find_best_cut_score`
   - `smart_bot_logic.should_accept_hu`
4. Continue new-rule-native bot submission through:
   - `server.gamestate.game_new_rule.get_action.get_ai_action`
   - or directly `game_state.submit_action(...)`
5. Status map for review/debugging:
   - `waiting_hand_action`: use hand-action bot logic.
   - `onlycut_after_action`: cut after chi/peng.
   - `waiting_action_after_cut`: hu/peng/gang/chi/pass decision.
   - `waiting_action_qianggang`: hu/pass decision.
6. Keep scheduling bot actions asynchronously instead of resolving them synchronously inside `wait_action`.
7. Keep the existing `_BOT_DELAY = 0.5` behavior.
8. Add tests for:
   - auto-cut bot delay path queues cut.
   - smart bot cut path queues legal cut.
   - bot pass after discard response.
   - bot chi/peng/gang response can be queued.
   - bot hu response can be queued.
   - bot action after END is ignored.

Minimum useful bot upgrade:

- Done: replaced synchronous `_default_bot_action` with async scheduled new-rule bot tasks.
- Done: for `user_id == 0`, implement auto-cut/pass.
- Done: for `user_id == 2`, reuse smart cut selection, while keeping discard-response choices conservative:
  - accept legal hu if allowed.
  - otherwise pass.
  - add chi/peng/gang smart decisions later.

Risk:

- If bots can hu/claim too aggressively, manual Unity testing becomes harder.
- Keep a dev setting or bot mode that uses passive bots for UI debugging.

## Phase F: Room And UI Polish

Status: dev-only.

- [x] Dev-only `新规则测试` room creation exists.
- [x] New-rule create-room path passes `game_round` through to backend.
- [x] Backend accepts `game_round` values 1 through 4; keep the `3` / west-round option supported rather than hiding it.
- [x] Password option is functionally wired for new-rule rooms through the common room password/join validation path.
- [x] "复式" / random seed is functionally wired for new-rule rooms through the shared random-seed system.
- [x] Tourist-limit option is functionally wired for new-rule rooms through the common join rejection path.
- [ ] Tips option is not functionally wired for new-rule rooms yet; Unity currently sends `tips = false` for new rule.
- [ ] Spectator option is not functionally wired for new-rule rooms yet; Unity and backend currently force `allow_spectator = false` for new rule.
- [ ] Replace temporary/dev room creation with official room config entry.
- [ ] Add display strings for new rule and sub-rule.
- [ ] Decide public room-list visibility.
- [ ] Add new-rule option to normal room filters.
- [ ] Add rule help / short description.
- [ ] Decide whether to implement or hide/disable the tips toggle for new-rule rooms.
- [ ] Decide whether to implement or hide/disable spectator support for new-rule rooms.

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

## 2026-07-05 Unity Smoke Fix Notes

- Fixed backend discard-claim ming-gang path so the supplement draw is exposed as `deal_gang_tile`, matching Guobiao/Qingque/Sichuan visible-action expectations. The internal draw already happened; the missing public `drawn_tile` on the returned window caused Unity to miss the gang-draw update.
- Fixed `waiting_ready` timeout semantics to match old rules: pending `ready` defaults to ready on timeout, and `ready` remains exempt from stale `action_tick` rejection.
- Final new-rule settlement now emits one `show_result` step per deferred winner, using `liuju_step = "settle_hu"` and `liuju_status_final` on the last winner.
- Unity's Sichuan endgame helper historically replaced the currently running step when a new `show_result` arrived, relying on Sichuan server-side sleeps for pacing. New rule sends final winner panels back-to-back, so new-rule settlement now uses a real FIFO queue while leaving Sichuan replacement behavior unchanged.
- New-rule multi-winner final settlement is intended to be time-sequential, not button-switched: intermediate winner panels auto-advance after their countdown/hold, and the final winner panel is the one that accepts confirmation/ready.
- Updated new-rule final settlement pacing: every winner panel gets an 8-second confirm window. Intermediate panels have a Continue/Confirm button that advances only the local Unity queue and does not send `ready`; timeout also advances locally. The last panel uses the same 8-second window, but click or timeout sends `ready` to the backend. The backend ready timeout is sized as `winner_count * 8s + 2s` so a three-winner final settlement has about a 24-second display window before automatic ready fallback.
- Important nuance for multi-panel new-rule settlement: the backend ready timeout is only a fallback for disconnect/no-client cases. If earlier winner panels are clicked through quickly, the final panel's visible 8-second countdown can expire before the backend aggregate timeout. Therefore the final new-rule panel must submit `ready` on its own countdown timeout, just as a click would, so the button does not grey out while the player waits for the longer backend fallback. This is intentionally limited to the new-rule final settlement panel; generic action/default timeouts still belong to the backend.
- Duplicate/late-ready caveat: because both Unity's final panel and the backend ready phase have timeout fallbacks, a `ready` can arrive after the backend has already auto-readied the player and advanced. New-rule action routing treats that as an idempotent late action: ignore it if the player is no longer waiting or if the current legal action list does not contain `ready`. This prevents harmless frontend/backend race timing from becoming error logs or accidental cross-window input. Unity's `SendAction` includes `action_tick`, but `ready` remains exempt from strict stale-tick rejection to preserve old-rule-style result-panel behavior; the legal-action-window check is the main guard.
- No-winner wall draw parity: when the hand ends with no deferred winners, new rule follows old non-Sichuan rules. Unity shows the simple `liuju` prompt through `EndLiujuPanel` with no confirm button/countdown, and the backend ready fallback uses `liuju_ready_wait_seconds()` (0.35s fade + 2s hold = about 2.35s) instead of the multi-winner settlement timeout.
- Added Unity `FanTextDictionary` entries for `new_rule/standard` fan ids, and fixed backend final settlement to send those stable ids even when settlement records also contain Chinese fan names, so final settlement can display per-fan values instead of `0`.
- Fixed Unity `hu_self` action compatibility: Unity sends `targetTile = 0` for the self-draw button, so the backend now treats non-positive `target_tile` as unspecified and infers the self-draw win tile from the player's latest hand tile. This is especially important for the third winner, where the hand should end immediately instead of crashing before final settlement.
- Backend verification passed: `.\.venv\Scripts\python.exe run_new_rule_tests.py` (10 scripts).
- Unity batchmode compile check later passed with Unity 6000.5.2f1; log ended with return code 0 and no C# compiler errors.

Next manual Unity checks:

1. Discard-claim ming-gang, added kong, and concealed kong: meld appears, supplement tile enters hand, remaining tile count updates.
2. Result panel continue: if the button times out, the next hand should still start.
3. Final fan list: fan names and fan values should show for new-rule final settlement.
4. Three-winner hand: final settlement should show each winner in order, each panel should stay up to 8 seconds or advance when Continue is clicked, and the next hand should not start until the last panel is confirmed or times out.
5. Third winner self-draw: clicking self-draw should immediately enter final settlement instead of freezing.

Rare-event Unity testing plan: ordinary play with bots has covered the common flow, but multi-ron and several context fans are too rare to rely on random play. Use `other/new_rule_debug_scenario_plan.md` for the dev-only scenario injection path. Backend scenarios now cover `multi_ron_2`, `multi_ron_3`, `rob_kong`, `rob_kong_multi_ron_2`, `same_tile_lockout`, `haitei`, `houtei`, `rinshan`, `heavenly_win`, `earthly_win`, and `nine_gates`; the backend route cancels the active live loop and drives the injected hand through a dev-only scenario loop before resuming normal play. The Unity table UI now creates a small `NR Debug` floating button for those scenarios; selecting a scenario collapses the panel so the table animation is visible. Manual Unity verification is partially complete: both visible `same_tile_lockout` branches have passed. Keep that path removable and do not mix scenario branches into production scoring or action resolution.

Same-tile lockout caveat: the visible `same_tile_lockout` scenario covers the simple pass/self-draw/same-discard/unlock branches. Backend tests additionally cover lock persistence through intervening pongs and the real robbing-kong case: a player passes a discard win, another player pongs that tile, later draws the fourth copy and attempts added kong, and the original passer must not receive `hu` for robbing kong until they have discarded again. This is a real reachable sequence, not a fifth-copy impossibility.

Robbing-kong visual parity: align this with Sichuan. An added-kong attempt should still broadcast the visible `jiagang` action before the `waiting_action_qianggang` response window. Unity then creates the fourth exposed kong tile through the existing `Change3DTile("jiagang")` path and stores it in `lastCutJiagang3DObject`; if the kong is robbed, the win presentation consumes that same object as the source tile. Do not replace this with a new-rule-only hidden hand-tile fallback, because that bypasses the old protocol and can leave the exposed meld/hand display out of sync. Backend rule state may still treat the kong as unfinalized/reverted when robbed; the Unity animation source should follow the old Sichuan visible-action path.

Multi-win presentation can need more visible copies of a tile than the real tile object pool has available, especially robbing-kong double wins where four physical copies may already be represented by hand/meld/kong objects. Do not clone a stale source tile for the extra presentation copy, because its material/logical state can be wrong; instead use a blank-pool object with the requested `hepai_tile` texture applied and a blank-pool return id. This keeps the visual face correct without consuming a fifth real tile object.

Mid-hand multi-win pacing: align with Sichuan backend timing shape. Sichuan broadcasts one mid-hand `show_result` per winner and then waits before sending the next winner panel or continuation draw. New rule mirrors that by inserting an internal outbound delay marker after each deferred mid-hand `show_result`; `flush_outbound_payloads()` sleeps for 0.5 seconds and never sends the marker to Unity. This keeps Unity's existing Sichuan-style single active presentation coroutine from being interrupted by back-to-back `show_result` messages. The delay is shorter than Sichuan's conservative 1.5 seconds because current win-tile travel is about 0.2 seconds; if low-frame-rate playtests still show interrupted animations, raise this toward the Sichuan value.

## 2026-07-06 Protocol Audit Notes

Main hu-class rule:

- Input action `"hu"` is still valid and should remain valid for discard-win and rob-kong response buttons.
- Settlement/display/record `hu_class` must not use bare `"hu"`. Unity result, replay, score history, sound, and action display expect:
  - `hu_self`
  - `hu_first`
  - `hu_second`
  - `hu_third`
- Important: in the existing project protocol, `hu_first` / `hu_second` / `hu_third` are relative-seat ron classes from the discarder/kong player, not "the first/second/third winner in a multi-ron sequence".
  - winner is the next seat after the discarder/kong player -> `hu_first`
  - winner is the opposite seat -> `hu_second`
  - winner is the previous seat -> `hu_third`
  - Therefore a single discard win can legitimately be `hu_third` if the winner sits in that relative seat.
- Fixed: new-rule final show-result payloads map discard/rob-kong wins to `hu_first` / `hu_second` / `hu_third`.
- Fixed: new-rule round recording now uses the same mapping instead of writing bare `"hu"` into record ticks.
- Checked: self-draw does not have the same problem. New rule uses `hu_self`, and Unity already recognizes `hu_self` in action buttons, result display, reveal presentation, sounds, replay, and score-history extraction.

Remaining old-rule-only Unity areas:

- `TileCard`, `TipsBlock`, and `TipsContainer` still calculate live tips only for existing rules. New-rule room creation currently sends `tips = false`, so this is not a core-play blocker, but the tips toggle must stay disabled/ignored until a new-rule client-side or server-fed tips path exists.
- `RecordChongHintCalculator` is old-rule-only. New-rule replay danger hints are not parity-ready.
- `RuleNameDictionary` and `SubRuleDescriptionDictionary` do not yet have polished new-rule labels/descriptions. This affects UI polish, not game flow.
- Fixed: score-history summary now uses a new-rule-specific display of `x fan / 6x points`, matching the rule concept that the winner's gain is `6x`. Discard win pays `6x`; self-draw splits that gain across the remaining payers.
