# 简单麻将（Jiandan）

`jiandan` 是简单麻将的正式规则标识。本目录记录 PR A 实际提交的规则、模块边界和番种说明。

## 本次范围

- 固定“一人和牌即止”，不提供第二/第三赢家续打选项。
- 服务端负责合法动作、和牌判定、番种、支付与最终结算。
- Unity 只增加建房/网络路由、静态显示配置，以及独立计算程序集中的本地听牌与悬停提示。
- 本地提示不包含海底、河底、杠上、抢杠、天和、地和等局面番，最终结果始终以服务端为准。

## 文档

- [规则定义](rule_reference.md)
- [实现边界](architecture.md)
- [番种计分表（中文）](fan_scoring.zh-CN.md) / [English](fan_scoring.md)
- [逐番详细说明（中文）](fan_details.zh-CN.md) / [English](fan_details.md)

## 代码入口

服务端：

- `server/game_calculation/jiandan`：牌型分解、番种、计分和听牌。
- `server/gamestate/game_jiandan`：简单动作、首家和牌终局、广播与对局生命周期。
- `server/database/jiandan`：规则专用的现有牌谱表适配。

Unity：

- `CalculationScript/Jiandan` 与 `JiandanExternal`：独立程序集内的客户端提示计算。
- `GameStateNetworkManager` / `RoomNetworkManager`：Jiandan 路由。
- 四个最小提示桥接点：`TipsBlock`、`TipsContainer`、`TileCard`、`RecordChongHintCalculator`。

## 明确不在本次范围

多阶段赢家动画、续打协议、主游戏流程重构、和牌结果布局修复均应另行沟通并单独提交 PR。
