# 新规则 README

这是自定义新规则工作的中文入口文档。上下文压缩、隔一段时间回来继续、或者从零 review 新规则时，建议先读这里。

## 当前 Pickup 入口

优先读：

- [新规则工作快照 - 2026-07-06](new_rule_work_snapshot_2026-07-06.md)

这份 snapshot 记录了当前 git 节点、已经能试玩到哪里、已经测试了什么、还没完成什么、以及推荐下一步。

当前已知关键提交：

- `bdd3d9f6 Snapshot new-rule Unity playtest state`
- 后续文档提交：`e34a8413 Document new-rule playtest snapshot`
- 文档索引提交：`5d85d6dd Add new-rule documentation index`

## 规则 Reference

核心规则定义：

- [新规则 Reference](new_rule_reference.md)
- [过水 / 同牌点和禁例说明](new_rule_discard_win_lockout.md)
- [一炮多响实现说明](new_rule_multi_ron_implementation.md)

番种与计分定义：

- [番种计分总表](new_rule_fan_scoring/new_rule_fan_scoring.md)
- [番种细节说明](new_rule_fan_scoring/new_rule_fan_details.md)

## 实现与测试计划

后端优先的实现计划：

- [新规则实现计划](new_rule_implementation_plan.md)
- [新规则本地测试计划](new_rule_local_test_plan.md)
- [新规则 live 集成边界](new_rule_live_integration_boundary.md)

协议与旧规则对齐：

- [旧规则对齐重构计划](new_rule_legacy_alignment_refactor_plan.md)
- [旧规则对齐审计](new_rule_legacy_alignment_audit.md)
- [协议对齐计划](new_rule_protocol_alignment_plan.md)

## Unity 试玩与 Debug

Unity parity 和手动测试记录：

- [Unity Parity Checklist](new_rule_unity_parity_checklist.md)
- [本地 Unity 试玩计划](local_unity_playtest_plan.md)

开发专用的稀有事件测试场景：

- [Debug Scenario Plan](new_rule_debug_scenario_plan.md)

当前 Unity 牌桌内有一个 `NR Debug` 浮动按钮，用来触发新规则稀有事件测试。它是开发专用入口，未来 upstream review 前应该保持可移除，或者放在明确的 dev-only guard 后面。

## 历史 Snapshot

- [工作快照 - 2026-07-05](new_rule_work_snapshot_2026-07-05.md)
- [工作快照 - 2026-07-06](new_rule_work_snapshot_2026-07-06.md)

当前应以 2026-07-06 snapshot 作为主要 handoff。2026-07-05 snapshot 主要用于了解更早期、Unity parity/debug 场景完善前的历史状态。

## 快速命令

后端 smoke tests：

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe run_new_rule_tests.py
```

Debug scenario 专项测试：

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe server\gamestate\game_new_rule\test_new_rule_debug_scenarios.py
```

启动本地后端：

```powershell
cd C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_server
.\.venv\Scripts\python.exe main.py
```

Unity 项目路径：

```text
C:\Users\changnan\Documents\open_mahjong_unity\open_mahjong_unity
```

打开场景：

```text
Assets/Scenes/MainScene.unity
```

## Review 注意事项

- 新规则需要优先复用青雀、国标、四川等旧规则已有的协议形状；不要轻易新增 Unity 专用字段。
- Python 后端应作为合法性、超时默认动作、计分、结算的 source of truth。
- 局中和牌不能提前公开番种列表、分数细节或隐藏信息；这些应延后到终局结算。
- `hu_first` / `hu_second` / `hu_third` 是相对点炮者或加杠者的座次分类，不是一炮多响里的第一个/第二个/第三个赢家。
- 同牌点和禁例也适用于抢加杠和。
- `NR Debug` / debug scenario UI 是开发工具，不应在最终公开版本中无保护地暴露。
