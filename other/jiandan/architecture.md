# 可组合麻将规则架构

## 目标

规则不等于一整套复制的状态机。一个可运行规则由四类组件装配：

1. Action policy：合法动作、响应优先级、多响和过和限制。
2. Settlement policy：牌型、番种、支付人与分数变化。
3. Hand-flow policy：第几家和牌后结束、赢家是否退出、下一活动玩家。
4. Presentation profile：客户端动画、延迟展示、结算队列和分数显示能力。

`RuleComposition` 只表达组合关系；实时状态机负责时序、连接和生命周期，不根据规则名推测模块行为。

## 当前简单装配

`JiandanActionPolicy`

+ `JiandanSettlementPolicy`

+ `WinContinuationPolicy(first_win | second_win | third_win)`

+ `PresentationProfile`

房间字段 `hand_end_mode` 的协议值为：

| 值 | 结束条件 | 赢家退出 |
| --- | --- | --- |
| `first_win` | 首次确认和牌后 | 否，本局立即结束 |
| `second_win` | 累计两家和牌后 | 是 |
| `third_win` | 累计三家和牌后 | 是 |

终局阈值在一个完整响应批次结算后判断，不截断同一张牌上的多家确认和牌。

## 未来血战国标

目标装配是：

`GuobiaoActionPolicy`

+ `GuobiaoSettlementPolicy`

+ `WinContinuationPolicy(third_win)`

+ continuous-winner `PresentationProfile`

国标番种、起和限制、动作选择和支付规则继续使用国标实现；只有 hand-flow 和展示能力发生替换。不得复制一份 `GuobiaoGameState`，也不得在 Unity 中增加“血战国标”规则名特判。

当前公共测试用非简单玩家对象验证 `WinContinuationPolicy` 只依赖 `player_index/is_hu`，用于固定这一边界。

## 扩展规则

新增动作差异时实现 action policy；新增支付差异时实现 settlement policy；新增续打模式时扩展 hand-flow；新增动画差异时扩展 presentation profile。协议消费者读取能力字段，不从 `roomRule` 反推流程。
