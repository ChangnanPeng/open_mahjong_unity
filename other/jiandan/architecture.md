# PR A 实现边界

## 权威边界

Python 服务端是简单麻将的权威实现。客户端计算只服务于即时提示，不参与最终合法性和结算决策。

服务端模块职责：

- `game_calculation/jiandan`：牌型、番种、听牌和分数计算。
- `gamestate/game_jiandan/action_check.py`：合法动作与响应优先级。
- `gamestate/game_jiandan/settlement.py`：支付矩阵。
- `gamestate/game_jiandan/JiandanGameState.py`：对局时序与固定首家和牌终局。
- `gamestate/game_jiandan/boardcast.py`：沿用普通客户端可消费的单次 `show_result` 协议。

## 固定首家和牌终局

- 自摸确认后立即结束本局。
- 弃牌或抢加杠存在多名可和玩家时，按责任玩家之后的固定座次选择最近的首个合法赢家（头跳）。
- 首个赢家确认后不再处理后续和牌响应，也不再发牌。
- 迟到或重复的和牌动作不能增加第二名赢家。
- 牌墙耗尽且无人和牌时按普通流局结束。

房间、`game_info` 和 `show_result` 不包含任何赢家阶段、续打或展示队列配置。

## Unity 允许域

Unity 只改动：

- 建房规则选项、房间配置显示和静态字典；
- `room/create_Jiandan_room` 与 `gamestate/jiandan/*` 路由；
- 已有 `CalculationScriptAssembly` 内的 Jiandan 提示计算；
- 四个从现有 UI/回放入口调用计算程序集的最小桥接点。

未修改 `Game3DManager*`、`NormalGameStateManager*`、`RoundEndPresentation*`、结果面板、分数历史或牌谱主流程。

## 后续扩展

若需要多阶段和牌、特殊动画或结果布局修复，应先确定协议和可复用公共方法，再分别提交独立 PR；PR A 不预埋这些能力字段。
