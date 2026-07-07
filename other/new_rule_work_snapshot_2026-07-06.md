# New Rule Work Snapshot - 2026-07-06

Purpose: preserve the current new-rule work state so future work can resume quickly after context compression, restart, or a break.

This snapshot corresponds to git commit:

- `bdd3d9f6 Snapshot new-rule Unity playtest state`

Important: the working tree may still show a local modification to `open_mahjong_server/server/chat_server/secret_key.txt`. That file was intentionally excluded from the snapshot commit and should not be treated as part of the new-rule work.

## One-Line State

The new rule is now locally playable in Unity with bots, uses old-rule-style protocol shapes much more closely than the earlier prototype, and has dev-only rare-event debug scenarios. The current best pickup point is to continue Unity parity/productization from `other/new_rule_unity_parity_checklist.md`, while using `other/new_rule_debug_scenario_plan.md` for rare-event manual tests.

## Environment And Paths

- Repo root: `C:\Users\changnan\Documents\open_mahjong_unity`
- Backend root: `C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server`
- Unity project root: `C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_unity`
- Python venv: `C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server\.venv\Scripts\python.exe`
- Unity editor: `C:\Program Files\Unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe`
- Unity version used locally: `6000.5.2f1`
- Backend game port: `8081`
- Backend chat port: `8083`

Useful restart flow:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity
netstat -ano | Select-String ':8081|:8083'
# Stop old python/cmd PIDs shown by netstat / process inspection.
Start-Process -FilePath 'C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server\.venv\Scripts\python.exe' -ArgumentList 'main.py' -WorkingDirectory 'C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server' -WindowStyle Hidden
Start-Sleep -Seconds 3
netstat -ano | Select-String ':8081|:8083'
```

PowerShell note: avoid brittle inline quoting. Prefer simple commands, explicit paths, and `Select-String` over complex chained snippets.

## Core Rule Decisions

The new rule currently follows these agreed design decisions:

- 136-tile wall with suits and honors.
- No flowers.
- No 14-tile dead wall; draw through the whole wall.
- No dingque.
- No chajiao.
- No immediate kong scoring.
- No cuohe/false-win flow.
- 0-fan/0-point wins are legal if the hand is a valid 4 melds plus 1 pair shape.
- Blood-battle flow:
  - one player winning does not end the hand.
  - winners exit the hand.
  - hand ends when 3 players have won or the wall is exhausted.
- Fixed dealer rotation every hand.
- Chi is physical-next-seat only, not next active player.
- After chi/peng, the player must discard before concealed kong or added kong.
- Mid-hand hu hides fan list and score details; final settlement reveals deferred fan details.
- Concealed kong follows Guobiao/Qingque-style hidden information.
- Robbing kong applies only to added kong.

Same-tile discard-win lockout:

- Passing a legal discard win on tile X locks discard-win on X.
- The lock lasts until the player next discards.
- Self-draw ignores the lock.
- Robbing an added kong is discard-win-like and is also blocked by the lock.
- When the player discards, old locks clear and the discarded tile becomes the new lock.
- This can happen through real pong/add-kong flow: a player may pass a discard win, another player pongs that tile, later draws the fourth copy, attempts added kong, and the original passer must not be able to rob it until they have discarded again.

## Main Files And Areas

Backend new-rule calculation:

- `open_mahjong_server/server/game_calculation/new_rule/`

Backend new-rule live state:

- `open_mahjong_server/server/gamestate/game_new_rule/NewRuleGameState.py`
- `open_mahjong_server/server/gamestate/game_new_rule/boardcast.py`
- `open_mahjong_server/server/gamestate/game_new_rule/get_action.py`
- `open_mahjong_server/server/gamestate/game_new_rule/bot.py`
- `open_mahjong_server/server/gamestate/game_new_rule/debug_scenarios.py`

Backend integration:

- `open_mahjong_server/server/gamestate/gamestate_router.py`
- room creation / hidden test room paths under backend room/gamestate code.

Unity new-rule integration:

- `open_mahjong_unity/Assets/Scripts/Network/GameStateNetworkManager.cs`
- `open_mahjong_unity/Assets/Scripts/Network/Serialize/Request.cs`
- `open_mahjong_unity/Assets/Scripts/GameScene/GameStateManager/NormalGameStateManager.*.cs`
- `open_mahjong_unity/Assets/Scripts/GameScene/3DManager/Game3DManager*.cs`
- `open_mahjong_unity/Assets/Scripts/GameScene/GameSceneUI/*.cs`
- `open_mahjong_unity/Assets/Scripts/GameScene/GameSceneUI/NewRuleDebugScenarioPanel.cs`
- config dictionaries for rule names, round text, fan names, and score history.

Key docs:

- `other/new_rule_reference.md`
- `other/new_rule_discard_win_lockout.md`
- `other/new_rule_fan_scoring/new_rule_fan_details.md`
- `other/new_rule_implementation_plan.md`
- `other/new_rule_legacy_alignment_refactor_plan.md`
- `other/new_rule_protocol_alignment_plan.md`
- `other/new_rule_unity_parity_checklist.md`
- `other/new_rule_debug_scenario_plan.md`
- `other/local_unity_playtest_plan.md`

## What Is Completed In This Snapshot

Backend:

- New-rule scoring/fan detection has a substantial implementation.
- 0-point legal win path is supported.
- Blood-battle hand lifecycle is implemented.
- Mid-hand hu settlement is deferred until final settlement.
- Same-tile discard-win lockout is implemented and tested.
- Robbing-kong lockout is implemented and tested.
- Added-kong, concealed-kong, discard-claim kong, supplement draw, haitei/houtei/rinshan/heavenly/earthly/nine-gates contexts have tests.
- New-rule bot path uses an async new-rule adapter instead of the earliest synchronous fallback.
- New-rule messages use old-rule-style protocol fields much more closely than the earlier prototype.
- Dev-only debug scenario route exists:
  - `gamestate/new_rule/debug_scenario`
  - host-only.
  - new-rule-only.
  - cancels the active live loop before injecting the scenario.

Unity:

- New-rule hidden/dev room can be created from Unity.
- Tourist login, adding 3 bots, starting game, table rendering, discarding, chi/peng/kong/hu-style interaction, and multi-round play have been exercised.
- `gamestate/new_rule/...` messages route into the normal table UI.
- `new_rule` final settlement can show new-rule fan ids and values instead of all-zero fan display.
- Multiple winner final settlement uses a queue so panels do not overwrite each other.
- Result-panel ready/timeout behavior was aligned enough for multi-panel new-rule settlement.
- Other-player mid-hand self-draw hidden tile presentation was fixed.
- Robbing-kong visual path was aligned with Sichuan-style visible added-kong action.
- Multi-win presentation can spawn a visible tile from blank-pool fallback when the real tile pool is exhausted.
- Seat wind display now updates across hands.
- `NR Debug` floating panel exists in-game for new-rule rare-event testing.

Debug scenarios currently implemented:

- `multi_ron_2`
- `multi_ron_3`
- `rob_kong`
- `rob_kong_multi_ron_2`
- `haitei`
- `houtei`
- `rinshan`
- `heavenly_win`
- `earthly_win`
- `nine_gates`
- `same_tile_lockout`

Manual Unity playtests passed before this snapshot:

- Ordinary new-rule gameplay with 3 bots.
- Multi-round play enough to find/fix several lifecycle issues.
- Robbing-kong double-win visual issue after the visible-blank fallback fix.
- Mid-hand multi-win pacing at `0.5s`.
- `same_tile_lockout` visible branch A:
  - pass first `5m`.
  - self-draw on `5m` is still available.
  - cutting `5m` keeps next same-tile ron blocked.
- `same_tile_lockout` visible branch B:
  - pass first `5m`.
  - cut a different tile.
  - next bot cuts `5m`.
  - ron is available again.

Verification at snapshot:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe run_new_rule_tests.py
```

Result:

- scoring: 34 tests ok
- service: 5 tests ok
- tingpai: 5 tests ok
- gamestate skeleton: 90 tests ok
- action_check: 9 tests ok
- get_action: 8 tests ok
- boardcast: 22 tests ok
- debug scenarios: 17 tests ok
- router: 6 tests ok
- gamestate_manager: 1 test ok
- room creation: 38 tests ok
- full new-rule backend smoke suite: 11 scripts ok

## What Is Not Done Yet

Unity parity and productization:

- Debug scenario buttons are dev-only and still need a cleanup/removal plan before upstream review.
- Not every rare-event scenario has been manually verified in Unity.
- The deeper same-tile lockout pong-chain/rob-kong branches are backend-tested but do not yet have separate deterministic Unity visual buttons.
- Reconnect behavior during active hand and after final settlement is not fully verified.
- Spectator support is not ready and should remain disabled/ignored until information leaks are audited.
- Tips option is not functionally wired for new-rule rooms.
- Public room-list exposure and polished official create-room UI are not done.
- Rule help / description UI is not product-ready.
- Full record/replay review is not complete.
- Existing-rule regression after the broad Unity routing changes still needs a deliberate pass.

Known local state:

- `open_mahjong_server/server/chat_server/secret_key.txt` may be modified locally and is intentionally not included in this snapshot.
- Batchmode log files named `unity_batchmode_check*.log` were cleaned before the snapshot commit.

## Best Next Steps

Recommended immediate next step:

1. Continue from `other/new_rule_unity_parity_checklist.md`.
2. Manually test remaining `NR Debug` scenarios:
   - `multi_ron_2`
   - `multi_ron_3`
   - `rob_kong`
   - `rob_kong_multi_ron_2`
   - `haitei`
   - `houtei`
   - `rinshan`
   - `heavenly_win`
   - `earthly_win`
   - `nine_gates`
3. Watch specifically for:
   - no interrupted tile animations.
   - correct hidden-information behavior.
   - correct final settlement panel order and timing.
   - correct fan ids and values.
   - correct score deltas and next-round/game-end lifecycle.

After rare-event smoke:

1. Decide whether to add separate scripted Unity buttons for the backend-only lockout chain cases:
   - immediate next-bot same-tile discard.
   - pong-then-later-same-tile discard.
   - pong-chain-then-added-kong where robbing kong is blocked.
2. Audit record/replay and score history.
3. Run old-rule regression:
   - Qingque
   - Guobiao
   - Sichuan
   - Classical
   - Riichi
4. Decide what to do with dev-only debug tooling:
   - keep behind a dev-only guard, or
   - remove before review using the cleanup steps in `other/new_rule_debug_scenario_plan.md`.
5. Prepare a review-friendly cleanup pass:
   - remove prototype naming where possible.
   - keep new-rule special cases narrow and documented.
   - confirm old-rule protocols were reused rather than duplicated.

## Important Cautions For Future Work

- Prefer existing rule protocol shapes over new custom fields.
- For general behavior such as timeouts/default actions, backend should remain the source of truth; Unity should mostly clean UI/input.
- `hu_first` / `hu_second` / `hu_third` are relative-seat ron classes from the discarder/kong player, not ordinal winner numbers.
- A single ron can legitimately be `hu_third`.
- Do not reveal mid-hand winner fan list or score details before final settlement.
- Do not reveal other players' real self-draw tile for mid-hand new-rule self-draw.
- Robbing-kong visual presentation should stay aligned with Sichuan's added-kong visible-action path.
- Presentation-only duplicate win tiles may use the blank-pool visible fallback; ordinary meld construction should not hide real object-pool problems with that fallback.
- The `0.5s` mid-hand multi-win pacing worked locally, but slower machines could need a larger delay.
- If Unity behavior seems odd, first compare Qingque/Guobiao/Sichuan implementation before writing new-rule-only code.

## Quick Pickup Commands

Backend tests:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe run_new_rule_tests.py
```

Focused debug scenario tests:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_debug_scenarios.py
```

Unity project:

```text
C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_unity
```

Open scene:

```text
Assets/Scenes/MainScene.unity
```

Manual Unity smoke:

1. Start backend.
2. Open Unity project and Play.
3. Tourist login.
4. Create hidden/dev new-rule room.
5. Add 3 bots.
6. Start game.
7. Use ordinary play or `NR Debug` scenarios depending on the test.
