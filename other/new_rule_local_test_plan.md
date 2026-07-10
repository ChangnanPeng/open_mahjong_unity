# New Rule Local Test Plan

This document records the minimum local testing route for developing the new rule set. The goal is to test Python backend rule logic first, without requiring Unity, web frontend, chat server, or database setup until later.

## Current Local State

- Workspace: `C:\Users\changnan\Documents\open_mahjong_unity`
- Backend root: `open_mahjong_server`
- Server entry point: `open_mahjong_server/main.py`
- Main FastAPI app: `open_mahjong_server/server/server.py`
- Python dependencies: `open_mahjong_server/requirements.txt`
- Declared stack in README: Python 3.12, FastAPI, PostgreSQL.

Observed on this machine before setup:

- `python --version` exited with code 1 and no useful output.
- `py --version` was not available.
- `where.exe python` resolved to `C:\Users\changnan\AppData\Local\Microsoft\WindowsApps\python.exe`, which is the Windows Store alias/stub, not a usable Python interpreter for backend tests.

Setup performed:

- Installed Python 3.12.10 with `winget`.
- The current shell still resolves `python` to the WindowsApps alias, so tests use the virtual environment interpreter directly.
- Created backend virtual environment at `open_mahjong_server/.venv`.
- Installed all dependencies from `open_mahjong_server/requirements.txt`.

Current conclusion: Python backend minimum tests can run through `open_mahjong_server/.venv/Scripts/python.exe`.

## Test Scope

For new-rule development, use three test levels:

1. Rule-calculation probe tests.
2. Game-flow unit/integration probes.
3. Optional full server/client integration.

The first two levels should not require Unity or a local database.

## Level 0: Environment Smoke Test

Purpose: confirm a real Python interpreter and dependency environment.

Recommended setup:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Minimum commands to verify:

```powershell
.\.venv\Scripts\python.exe -c "import fastapi, pydantic, websockets; print('core deps ok')"
.\.venv\Scripts\python.exe -c "import mahjong; print('mahjong dep ok')"
```

Expected result:

- Both commands print success messages.
- If `pythonnet` or C# Qingque bridge fails later, it does not block the Python-only new-rule route.

Actual result:

- `core deps ok`
- `mahjong dep ok`

## Level 1: Original Code Import Probes

Purpose: confirm the existing backend rule modules can import before any new-rule code is added.

Run from `open_mahjong_server`:

```powershell
.\.venv\Scripts\python.exe -c "from server.game_calculation.game_calculation_service import GameCalculationService; print('GameCalculationService import ok')"
.\.venv\Scripts\python.exe -c "from server.gamestate.game_sichuan.SichuanGameState import SichuanGameState; print('SichuanGameState import ok')"
.\.venv\Scripts\python.exe -c "from server.gamestate.game_guobiao.action_check import check_action_after_cut; print('Guobiao action_check import ok')"
```

Notes:

- Importing `server.server` is not the first target because it constructs `DatabaseManager` and the full `GameServer` at import time.
- Full server startup will need PostgreSQL and chat-server details; it is not required for minimum rules work.

Actual result:

- `GameCalculationService import ok`
- `SichuanGameState import ok`
- `Guobiao action_check import ok`

## Level 2: Original Calculation Probes

Purpose: call existing calculation functions directly, without the full server.

Suggested first probes:

```powershell
.\.venv\Scripts\python.exe -c "from server.game_calculation.guobiao_hepai_check import Chinese_Hepai_Check; c=Chinese_Hepai_Check(); print(c.hepai_check([11,12,13,21,22,23,31,32,33,41,41,45,45,45], [], ['自摸'], 45))"
.\.venv\Scripts\python.exe -c "from server.game_calculation.sichuan.sichuan_hepai_check import Sichuan_Hepai_Check; c=Sichuan_Hepai_Check(); print(c.hepai_check([11,11,11,12,13,14,21,22,23,31,32,33,39,39], [], ['自摸'], 39, 0))"
```

The exact fan names may display incorrectly if terminal encoding is not UTF-8, but the call should return a result tuple and not crash.

Actual result:

- Guobiao direct calculation succeeded and returned `(24, ['三色三同顺', '五门齐', '全带幺', '不求人', '箭刻'])` for the first probe.
- Sichuan direct calculation was callable, but the ad-hoc sample returned `(0, ['Ć˝şÍ'])`; treat this as a callable smoke test only, not a semantic assertion.

## Level 3: New Rule Scoring Tests

After adding the new scoring module, create direct tests first. Recommended path:

```text
open_mahjong_server/server/game_calculation/new_rule/
```

Recommended test file path:

```text
open_mahjong_server/server/game_calculation/new_rule/test_new_rule_scoring.py
```

Initial test groups:

- Standard hand decomposition: sequences, triplets, pair.
- Seven pairs, including repeated-pair shape.
- Thirteen orphans, explicitly not mixed terminals.
- True nine-gates pre-win shape.
- Row maximum handling, including non-overlapping-unit scoring for the three-suit-number row.
- Three-suit-number regression: `小三色同刻` plus a disjoint `二色同刻`; multiple disjoint `二色同刻`; multiple disjoint `二连刻`.
- Timing fans: haitei/houtei, rinshan/chankan.
- Kong count row.

Run with either plain Python assertions or `pytest`. If no test framework is added, keep the first version as plain scripts to reduce dependency churn.

## Level 4: New Rule Flow Probes

After scoring is stable, add game-flow probes around a new game state skeleton.

Minimum cases:

- One player wins and exits; hand continues.
- Three players win; hand ends.
- Wall exhausts; hand ends.
- Winner's hand/fans/score are hidden until final settlement.
- Multiple discard winners make independent choices.
- Same-tile discard-win lockout blocks discard win and robbing-kong win, but not self-draw.
- After chi/peng, player must discard before any concealed/add kong.
- Final discard after empty wall can only be won; no chi/peng/kong.

## Level 5: Full Server and Client

This is optional and should be delayed.

Full FastAPI startup likely needs:

- Real Python 3.12 environment.
- Python dependencies installed.
- PostgreSQL configured according to `server/test_config.py` or local config.
- Chat server behavior reviewed; current test config has `auto_create_chatserver = True`.
- Unity or web client only if UI integration is being tested.

For rule-engine development, avoid this level until Python-only scoring and flow probes are green.

## Current New-Rule Backend Smoke Tests

Run from `open_mahjong_server`:

```powershell
.\.venv\Scripts\python.exe run_new_rule_tests.py
```

This is the preferred quick regression command. It runs the individual scripts below in order and stops on the first failure.

```powershell
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

The room-creation test covers the hidden backend-only `room/create_NewRule_room` path. It does not require Unity or a real database.
It also includes an in-process protocol smoke that dispatches:

```text
room/create_NewRule_room -> room/start_game -> gamestate/new_rule/cut_tile
```

This mirrors the business-router path used after a real WebSocket login, without starting the full FastAPI lifespan or database-backed login flow.
It also covers several connected scripted flows, including blood-battle continuation after discard win/self-draw/kong actions and final-discard wall exhaustion ending with final-settlement payloads.

## Current Blocker

No current blocker for Python-only minimum backend tests.

Remaining caveats:

- The current shell PATH still points `python` at the WindowsApps alias. Use `.\.venv\Scripts\python.exe` from `open_mahjong_server`, or open a fresh terminal after installation.
- Full FastAPI server startup is intentionally not part of the minimum path yet because it pulls in database and chat-server setup.

Recommended next action:

1. Keep extending Python-only scoring and game-state tests for rule changes.
2. Use the protocol-level room-creation test for smoke coverage of router wiring.
3. Only move to a full FastAPI/WebSocket smoke when database/login setup is part of the thing being tested.
