# New Rule Dev-Only Debug Scenario Plan

Last updated: 2026-07-06.

Purpose: add a clean, removable way to trigger rare live-game situations in Unity for the new rule. This is not a production feature. It exists only to verify that the normal live flow, Unity animation, result panels, score changes, and next-round lifecycle behave correctly in cases that are too rare to reach by ordinary play with bots.

## Design Goal

Build a dev-only scenario injection path for `room_rule = "new_rule"` test rooms.

The scenario should set the current hand into a deterministic near-trigger state, then let the normal game flow handle the important action. For example, a multi-ron scenario should still require the player to discard the target tile, after which the normal discard-response, bot response, settlement, result-panel, and ready/next-round paths run.

This is better than a script that directly jumps to settlement, because it tests the real live protocol and Unity integration.

## Current Status

Implemented backend-only pieces:

- `server/gamestate/game_new_rule/debug_scenarios.py`
- `server/gamestate/game_new_rule/test_new_rule_debug_scenarios.py`
- Host-only router route: `gamestate/new_rule/debug_scenario`
- Unity network helper: `GameStateNetworkManager.SendNewRuleDebugScenario(string scenario)`
- Unity in-game floating panel: `NewRuleDebugScenarioPanel` creates an `NR Debug` button inside the table UI for every implemented scenario name below.

Implemented scenario names:

- `multi_ron_2`: player 0 can discard the target tile, then players 1 and 2 can ron through the normal discard-response flow.
- `multi_ron_3`: player 0 can discard the target tile, then players 1, 2, and 3 can ron, ending the hand through the normal final-settlement flow.
- `rob_kong`: player 0 can declare added kong, then player 1 can rob the kong through the normal qianggang response flow.
- `rob_kong_multi_ron_2`: player 0 can declare added kong, then players 1 and 3 can both rob the kong; this covers the lower-seat and upper-seat two-winner robbing-kong case.
- `haitei`: player 0 can self-draw on an empty wall and score `haitei`.
- `houtei`: player 0 can discard the final tile, then player 1 can ron and score `houtei`.
- `rinshan`: player 0 can declare concealed kong, draw the supplement tile, then self-draw and score `rinshan`.
- `heavenly_win`: dealer can immediately self-draw and score `heavenly_win`.
- `earthly_win`: non-dealer can self-draw on their first natural draw and score `earthly_win`.
- `nine_gates`: player 0 can self-draw from the true nine-wait shape and score `nine_gates`. This scenario also supports manual discard-win and same-tile lockout checks: skip self-draw, discard `5m`, then player 1 draws and cuts `9m`, allowing player 0 to test ron; or skip self-draw, discard `9m`, then player 1 draws and cuts `9m`, where player 0 should be blocked by same-tile lockout. Because the nine-gates shape naturally contains `999m`, the `9m` discard may also expose peng/gang options alongside hu/pass; choose hu/pass for the intended test.
- `same_tile_lockout`: player 3 auto-cuts `5m`; player 0 can win but should choose pass, locking `5m`. Player 0 then draws `5m` and should still be allowed to self-draw because self-draw ignores discard-win lockout. If player 0 cuts `5m`, player 1 auto-draws and auto-cuts `5m`; player 0 should not receive a discard-win `hu` prompt on that same tile. If player 0 cuts a different tile such as `1m`, the old `5m` lock should clear/restart on the newly cut tile, and player 0 should be able to ron player 1's next `5m`. Backend regression tests also cover three longer same-tile lockout chains: player B cuts a tile, player 0 passes, then player C immediately cuts the same tile and player 0 remains locked; player D cuts a tile, player 0 passes, player B pongs it, then player C later cuts the same tile and player 0 remains locked; player D cuts a tile, player 0 passes, player C pongs it, player D later cuts a different tile that player B pongs, then player C draws the locked tile and attempts added kong, where player 0 is still blocked from robbing the kong.

Backend validation passed:

- `.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_debug_scenarios.py`
- `.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_router.py`
- `.\.venv\Scripts\python.exe run_new_rule_tests.py`

Unity visible UI is wired through an in-game floating `NR Debug` button. It appears only during a non-spectator new-rule game. Click it to open the scenario list; selecting a scenario immediately collapses the list so it does not block the table animation.

Manual Unity verification status:

- Passed: `same_tile_lockout` visible branch A. After player 0 passes the first `5m`, self-draw on `5m` is still offered, then cutting `5m` keeps player 0 locked when the next bot cuts `5m`.
- Passed: `same_tile_lockout` visible branch B. After player 0 passes the first `5m`, cutting a different tile clears the old `5m` lock/restarts the lock on the newly cut tile, and player 0 can ron the next bot's `5m`.
- Backend-only coverage: the longer pong-chain and robbing-kong lockout branches are covered by deterministic tests. They are not yet exposed as separate Unity visual buttons because ordinary bot claim decisions are not deterministic enough for stable manual testing.

Important implementation note: the route must not directly mutate a live game while the normal game task is waiting inside an old `resolve_action_window()`. The backend route now uses a dev-only driver: it cancels the active `game_task`, starts a fresh round record for the injected hand, applies the scenario, flushes the injected payloads, then runs a scenario loop that resolves the injected window. After that debug hand ends, it uses the normal ready/next-round lifecycle and resumes the normal new-rule `run_game_loop()`.

Manual Unity steps for `same_tile_lockout`:

1. Click `same_tile_lockout`.
2. Wait for player 3 to auto-cut `5m`.
3. Player 0 should see `hu/pass`; click pass.
4. Player 0 should immediately draw `5m` and still see `hu_self`. This confirms self-draw is not blocked by discard-win lockout.
5. Branch A, continued same-tile lock: do not self-draw. Cut `5m`.
6. Player 1 should auto-draw and auto-cut `5m`.
7. Player 0 should not see a discard-win `hu` prompt on that `5m`.
8. Branch B, unlock after next cut: restart `same_tile_lockout`, pass the first `5m` again, then when player 0 draws `5m`, cut a different tile such as `1m`.
9. Player 1 should auto-draw and auto-cut `5m`.
10. Player 0 should now see a discard-win `hu` prompt on that `5m`.

This scenario intentionally avoids chi/peng/gang side prompts around the visible `5m` branch, so the visible result should be attributable to same-tile lockout rather than claim priority. It covers pass-on-discard lock creation, self-draw bypass, own-discard clearing/restarting the lock, continued same-tile lock when the player cuts the same tile, and unlock/ron when the player cuts a different tile before the next same-tile discard.

Important correction: robbing-kong lockout can occur in a real hand. The player can pass a discard win on a tile, that tile can be claimed as a pong by another player, and later the pong owner can draw the fourth copy and attempt added kong. In that case the original passer is still locked from winning on that same tile until they next discard. The backend test `test_same_tile_lockout_survives_peng_chain_and_blocks_robbing_added_kong` covers this exact flow. If visual Unity coverage is needed later, add a more scripted debug runner for this branch rather than relying on ordinary bot claim decisions.

## Scope

Backend first:

- Done: add `server/gamestate/game_new_rule/debug_scenarios.py`.
- Done: add focused tests in `server/gamestate/game_new_rule/test_new_rule_debug_scenarios.py`.
- Done: add a small new-rule-only router entry: `gamestate/new_rule/debug_scenario`.
- Done: host-only and new-rule-only route guard.
- Done: scenario names are explicit strings; unknown names are rejected.
- Done: route cancels the old live loop before injecting the scenario, then drives the injected scenario through normal action resolution.

Unity second:

- Done: use a small runtime-created in-game floating panel instead of the login-page `TestPanel`.
- Done: the UI only sends the scenario name to the backend.
- Done: the UI is removable by deleting `NewRuleDebugScenarioPanel.cs` and the route helper; it is not part of room creation or public play.
- Pending: manual Unity playtest of the remaining rare-event scenario buttons. The core `same_tile_lockout` visible branches have passed.

## Candidate Scenarios

Implemented high priority:

- `multi_ron_2`: one discard lets two opponents win.
- `multi_ron_3`: one discard lets all three opponents win and immediately ends the hand.
- `rob_kong`: a player attempts added kong and another player can rob it.
- `rob_kong_multi_ron_2`: a player attempts added kong and two opponents rob it at once.
- `haitei`: wall has one tile; current player draws the last tile and self-draws.
- `houtei`: wall is exhausted by the draw; the following discard can be won.

Next priority:

- `rinshan`: kong supplement draw wins and scores `杠上开花`.
- `heavenly_win`: dealer opening hand can self-draw win immediately.
- `earthly_win`: non-dealer first natural draw can self-draw win before any chi/peng/kong.
- `nine_gates`: set the required nine-gates waiting shape and verify final fan detection/display.
- `same_tile_lockout`: player passes a discard win, verifies self-draw is still legal on the locked tile, verifies cutting the same tile keeps the same-tile ron blocked, verifies cutting a different tile unlocks the old tile so the next same-tile discard can be won, and verifies the lock persists through intervening pongs and can block robbing an added kong.

Optional later:

- `zero_point_win`: legal 4-melds-plus-pair win with no scored fan.
- `wall_draw_no_winner`: force no-winner wall exhaustion and verify simple `liuju` prompt plus 2.35s backend ready fallback.

## Implementation Shape

Each scenario function should:

- Clear pending actions, bot tasks, live windows, and transient action flags.
- Set `game_status`, `current_player_index`, `dealer_index` if needed.
- Set all four hands, melds, discards, scores, `is_hu`, waiting tiles, and wall.
- Recompute or explicitly set `waiting_tiles` where the scenario depends on win availability.
- Emit a normal refresh/start-style payload so Unity sees the injected state.
- Open the next normal action window instead of directly resolving the rare event.

Do not:

- Put scenario-specific branches inside scoring logic.
- Put scenario-specific branches inside normal action resolution.
- Mutate production room creation defaults.
- Enable this route for public rooms or spectators.

## Validation Checklist

For every debug scenario:

- Backend unit test proves the injected state is legal enough to open the expected next action window.
- Unity can enter the scenario from a new-rule test room.
- The rare action is then performed through normal player/bot actions.
- Result panels, score changes, `ready`, next hand, and final game end still use the normal code paths.
- Existing new-rule tests still pass.

For multi-ron specifically:

- Eligible players receive simultaneous `hu/pass` windows.
- Click timing does not change accepted-winner order.
- `hu_first` / `hu_second` / `hu_third` remain relative-seat classes from the discarder, not winner ordinal numbers.
- If the hand continues, the next draw starts after the last accepted winner in fixed seat order, skipping players who already won.
- If the third player wins, no mid-hand result panel is sent; final settlement panels are sent.

## Cleanup Plan

This feature must be removable as one dev-only block.

Future cleanup steps:

1. Delete `server/gamestate/game_new_rule/debug_scenarios.py`.
2. Delete `server/gamestate/game_new_rule/test_new_rule_debug_scenarios.py`.
3. Remove the `gamestate/new_rule/debug_scenario` branch from `server/gamestate/gamestate_router.py`.
4. Remove any request/response helper added for this route.
5. Delete `open_mahjong_unity/Assets/Scripts/GameScene/GameSceneUI/NewRuleDebugScenarioPanel.cs`.
6. Remove any scene/prefab references to the debug UI.
7. Remove links to this plan from:
   - `other/local_unity_playtest_plan.md`
   - `other/new_rule_unity_parity_checklist.md`
8. Run:
   - `.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_gamestate.py`
   - `.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_room_creation.py`
   - `.\.venv\Scripts\python.exe run_new_rule_tests.py`
   - Unity batchmode compile check.

Review rule: if any debug scenario code is referenced by production new-rule flow after cleanup, cleanup is incomplete.
