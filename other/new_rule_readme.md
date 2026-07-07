# New Rule README

This is the entry point for the custom new-rule work. Start here after a context reset or when reviewing the new rule from scratch.

## Current Pickup Point

Read this first:

- [New Rule Work Snapshot - 2026-07-06](new_rule_work_snapshot_2026-07-06.md)

That snapshot records the current git snapshot, what is playable, what has been tested, what is unfinished, and the recommended next steps.

Latest known snapshot commit:

- `bdd3d9f6 Snapshot new-rule Unity playtest state`
- follow-up documentation commit: `e34a8413 Document new-rule playtest snapshot`

## Rule Reference

Core rule definition:

- [New Rule Reference](new_rule_reference.md)
- [Discard-Win Lockout Notes](new_rule_discard_win_lockout.md)
- [Multi-Ron Implementation Notes](new_rule_multi_ron_implementation.md)

Fan and scoring definition:

- [Fan Scoring Summary](new_rule_fan_scoring/new_rule_fan_scoring.md)
- [Fan Details](new_rule_fan_scoring/new_rule_fan_details.md)

## Implementation And Test Plans

Backend-first implementation plan:

- [New Rule Implementation Plan](new_rule_implementation_plan.md)
- [New Rule Local Test Plan](new_rule_local_test_plan.md)
- [New Rule Live Integration Boundary](new_rule_live_integration_boundary.md)

Protocol and old-rule alignment:

- [Legacy Alignment Refactor Plan](new_rule_legacy_alignment_refactor_plan.md)
- [Legacy Alignment Audit](new_rule_legacy_alignment_audit.md)
- [Protocol Alignment Plan](new_rule_protocol_alignment_plan.md)

## Unity Playtest And Debug

Unity parity and manual test tracking:

- [Unity Parity Checklist](new_rule_unity_parity_checklist.md)
- [Local Unity Playtest Plan](local_unity_playtest_plan.md)

Dev-only rare-event debug scenarios:

- [Debug Scenario Plan](new_rule_debug_scenario_plan.md)

The current debug scenario entry is the in-game `NR Debug` floating panel. It is dev-only and should remain removable before upstream review.

## Historical Snapshots

- [Work Snapshot - 2026-07-05](new_rule_work_snapshot_2026-07-05.md)
- [Work Snapshot - 2026-07-06](new_rule_work_snapshot_2026-07-06.md)

Use the 2026-07-06 snapshot as the current handoff. The 2026-07-05 snapshot is useful historical context from before the later Unity parity/debug-scenario work.

## Quick Commands

Backend smoke tests:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe run_new_rule_tests.py
```

Focused debug scenario tests:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_debug_scenarios.py
```

Start local backend:

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe main.py
```

Unity project:

```text
C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_unity
```

Open scene:

```text
Assets/Scenes/MainScene.unity
```

## Review Cautions

- Prefer existing Qingque/Guobiao/Sichuan protocol shapes before adding new-rule-only Unity fields.
- Keep Python backend as the source of truth for legality, timeout/default actions, scoring, and settlement.
- Do not reveal mid-hand fan details or hidden tiles before final settlement.
- `hu_first`, `hu_second`, and `hu_third` are relative-seat ron classes from the discarder/kong player, not ordinal winner numbers.
- Same-tile discard-win lockout also applies to robbing added kong.
- The debug scenario UI is for development and should be easy to remove or keep behind a dev-only guard.
