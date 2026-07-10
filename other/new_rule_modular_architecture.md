# 可组合麻将规则架构

## 目标

规则不再等于一整套复制的状态机。一个可运行规则由四类模块组合：

1. **行动规则（Actions）**：能否吃、碰、杠、和；过和限制；多家响应如何取舍。
2. **计分规则（Settlement）**：番种识别、分值、付款人以及分数变更。
3. **终局流程（Hand Flow）**：第一、第二或第三家和牌后结束；已和玩家是否退场；牌山耗尽是否结束。
4. **展示能力（Presentation）**：中途和牌动画、是否延迟展示番种与分数、终局面板是否逐家排队、分数显示单位。

状态机只负责通用编排：摸牌 -> 询问行动 -> 收集响应 -> 调用行动模块 -> 调用计分模块 -> 调用流程模块决定继续或结束 -> 广播带展示能力的数据。

## 当前装配

`new_rule` 当前等价于：

```text
NewRuleActionPolicy
+ NewRuleSettlementPolicy
+ WinContinuationPolicy(first_win | second_win | third_win)
+ PresentationProfile
```

`WinContinuationPolicy` 和 `PresentationProfile` 位于服务端公共目录，不依赖 `new_rule`。客户端也读取 `hand_flow` 和 `presentation_profile`，而不是通过 `roomRule == "new_rule"` 猜测流程。

## 三种终局模式

| 选项 | 协议值 | 结束条件 | 已和玩家退场 |
| --- | --- | --- | --- |
| 和牌即止（普通） | `first_win` | 第一家确认和牌后 | 否（本局立即结束） |
| 二人和牌 | `second_win` | 累计两家和牌后 | 是 |
| 三人和牌（血战到底） | `third_win` | 累计三家和牌后 | 是 |

流程策略只给出本局还剩几个“和牌名额”，行动响应策略负责从同一张牌的候选人中选择谁占用名额。这样 `first_win` 和 `second_win` 不会因同一响应帧的一炮多响超过目标人数；而接受全部、座次截胡或三家和流局仍然属于**行动响应策略**，不藏进计分模块。当前 `new_rule` 依照既有物理座次响应顺序分配剩余名额；未来可以独立替换为国标或日麻的响应策略。

## 血战国标应如何组合

目标不是新建 `game_guobiao_blood_battle` 并复制所有文件，而是：

```text
GuobiaoActionPolicy
+ GuobiaoSettlementPolicy
+ WinContinuationPolicy(third_win)
+ continuous-winner PresentationProfile
```

国标番种、起和限制和付款规则保持不变。仅当玩家和牌后，公共流程模块把玩家标记为退场并选择下一名活动玩家；客户端依据展示能力播放中途和牌动画和延迟结算。若血战国标需要不同的自摸付款方式，那是一个新的国标结算策略参数，而不是新流程。

## 与长沙麻将接入方式的对比

长沙规则的新增覆盖了完整链路，并带有集中测试，这是值得沿用的部分：

- 独立计算包和听牌/和牌检查；
- 房间验证、路由、状态管理、数据库注册完整；
- Unity 配置和运行时创建选项齐全；
- 规则边界用测试固定。

但长沙仍复制了完整的 `ChangshaGameState.py`、`wait_action.py` 和 `boardcast.py`。这说明当前主干的注册层仍以规则名为中心，也正是 `new_rule` 不应继续照抄的部分。后续公共引擎成熟后，长沙也可以逐步迁移到同一组合模型，但本次不改变长沙行为。

## 协议

`game_info` 新增：

```json
{
  "hand_end_mode": "second_win",
  "winner_target": 2,
  "hand_flow": {
    "mode": "second_win",
    "winner_target": 2,
    "winners_exit_hand": true
  },
  "presentation_profile": {
    "winner_exit_animation": true,
    "defer_win_details": true,
    "result_sequence": "winner_sequence",
    "score_display_multiplier": 6,
    "draw_slot_win_tile": true,
    "complete_discard_before_ron": true,
    "concealed_win_tile": true,
    "preserve_win_animation_on_resume": true
  }
}
```

旧客户端仍可读取 `blood_battle`；新客户端以结构化能力为准。

## 后续拆分顺序

1. 将 `apply_action_results` 中的响应优先级和多响处理移入公共响应解析器。
2. 将通用摸牌、行动窗口、超时和活动玩家推进抽成 hand engine。
3. 把录像、重连和广播 envelope 从 `NewRuleGameState` 移到公共编排层。
4. 为国标创建薄的 action/settlement adapter，并用组合测试验证 `first_win` 与 `third_win`。
5. 主干稳定后，让 `GameStateManager` 使用规则注册表，减少每增加一个规则就修改多处 `elif`。

本阶段保留 `NewRuleGameState` 作为编排外壳，避免一次性重写实时对局；但流程决策、合法行动、计分和展示契约已经有独立替换点。
