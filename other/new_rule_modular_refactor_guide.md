# New Rule 模块化架构

本文说明 `new_rule` 当前的实现边界、如何切换和牌终局流程，以及未来如何把流程能力接入其他规则。目标是：**新规则由可替换模块组合而成，而不是复制一整套前后端状态机。**

## 一图理解

```text
房间配置 hand_end_mode
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ NewRuleGameState（编排层）                                    │
│ 摸牌 → 收集行动 → 执行动作 → 结算 → 判断是否继续本局 → 广播     │
└───────┬────────────────┬─────────────────┬──────────────────┘
        │                │                 │
        ▼                ▼                 ▼
 ActionPolicy      SettlementPolicy   WinContinuationPolicy
 合法行动/响应      番种、支付、分差    第几家和牌后结束、谁退场
        │                │                 │
        └────────────────┴─────────────────┘
                         │
                         ▼
                PresentationProfile
          将流程能力描述为前端展示/动画协议
                         │
                         ▼
             Unity RuleCapabilities + 通用 UI/动画
```

## 四个模块

| 模块 | 当前实现 | 职责 | 不应负责的事 |
| --- | --- | --- | --- |
| 行动规则 | `NewRuleActionPolicy` | 吃、碰、杠、和是否合法；行动候选；响应优先级/名额使用 | 番种计分、何时终局、Unity 动画 |
| 计分规则 | `NewRuleSettlementPolicy` | 和牌明细、支付方、分数变化、结算数据 | 决定是否血战继续 |
| 终局流程 | `WinContinuationPolicy` | 第 1/2/3 家和牌时是否结束；已和玩家是否退出；下一活动玩家 | 具体番种与支付方式 |
| 展示能力 | `PresentationProfile` | 给客户端声明中途和牌、延迟展示分数、和牌牌张布局等能力 | 根据规则名写特判 |

`RuleComposition` 把以上模块聚合为一个明确的规则装配对象。当前 `NewRuleGameState` 仍是状态机外壳，负责时序、房间和广播；模块负责规则决策。因此这是渐进式重构，不会一次性重写实时对局引擎。

## 可选和牌流程

房间字段为 `hand_end_mode`：

| UI 文案 | 协议值 | 目标和牌人数 | 和牌者是否退出本局 |
| --- | --- | ---: | --- |
| 和牌即止（普通） | `first_win` | 1 | 否，本局立即结束 |
| 二人和牌 | `second_win` | 2 | 是 |
| 三人和牌（血战到底） | `third_win` | 3 | 是 |

`WinContinuationPolicy.winner_slots_remaining` 是一个关键边界：同一张弃牌可能出现多个和牌响应，但流程只允许消耗剩余名额。这样 `first_win`、`second_win` 不会因“一炮多响”超过目标人数；至于国标头跳、多响、三家和流局等响应取舍，仍应由行动模块决定。

## 已落地的代码改动

### 服务端公共层

- `open_mahjong_server/server/gamestate/public/win_continuation.py`
  - `HandEndMode`、`WinContinuationPolicy`；兼容旧的 `blood_battle` 配置。
- `open_mahjong_server/server/gamestate/public/presentation_profile.py`
  - 将前端所需的展示差异变为结构化能力。
- `open_mahjong_server/server/gamestate/public/rule_composition.py`
  - `RuleComposition(actions, settlement, hand_flow, presentation)`。

### New Rule 服务端

- `game_new_rule/action_check.py`：`NewRuleActionPolicy` 门面。
- `game_new_rule/settlement.py`：`NewRuleSettlementPolicy`，从状态机迁出得分与支付逻辑。
- `game_new_rule/NewRuleGameState.py`：创建并调用四类模块；对弃牌和加杠响应按剩余和牌名额截断。
- `game_new_rule/boardcast.py`：在 `game_info` 广播中携带流程与展示能力。
- `room_validators.py`、`room_manager.py`、`room_router.py`、`server.py`：校验、保存并透传 `hand_end_mode`。

### Unity 客户端

- `Network/Serialize/Response.cs`
  - `GameInfo` 新增 `hand_end_mode`、`winner_target`、`hand_flow`、`presentation_profile`。
- `NormalGameStateManager.Initialization.cs`
  - 读取能力协议，而不是只通过 `roomRule == "new_rule"` 推断流程。
- `NormalGameStateManager.RuleCapabilities.cs`
  - 集中提供 `UsesWinnerExitFlow()`、`UsesWinnerResultSequence()`、`ScoreDisplayMultiplier()` 等查询。
- `RoundEnd`、`RoundEndPresentation`、`SichuanHu`、`EndResultPanel`
  - 根据能力驱动续打、结果队列、牌张展示与分数单位。
- 创建房间 UI
  - new rule 新增“终局流程”下拉框，配置保存到 `NewRule_Create_RoomConfig` 并随建房请求发送。

## 前后端协议

`game_info` 的典型数据：

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

旧客户端可继续读取 `blood_battle`；新客户端优先使用上述结构化字段。新增展示差异时，应先扩展 `PresentationProfile` 和 DTO，再由 Unity 的能力查询方法消费，避免再添加 `IsNewRule()` 专用分支。

## 如何改一个模块

### 只改计分

例如 new rule 的番种或支付方式变化：

1. 在 `NewRuleSettlementPolicy` 添加/替换计算方法；
2. 保持输出结算数据结构稳定（赢家、分差、支付方、番种说明）；
3. 为新计分添加服务端单元测试；
4. 不修改 `WinContinuationPolicy`，除非终局人数规则也改变。

这使得“相同流程，不同计分”成为小范围改动。

### 只改行动规则

例如改一炮多响、过胡、抢杠或可鸣牌限制：

1. 在 `NewRuleActionPolicy`（或新的 ActionPolicy）实现候选和响应选择；
2. 让选择逻辑尊重 `winner_slots_remaining`；
3. 添加同一弃牌多响应、流程名额不足等组合测试；
4. 不在结算模块中隐藏行动优先级判断。

### 新增流程模式

如果“第 N 家和牌结束”以外出现新的流程：

1. 扩展 `HandEndMode` / `WinContinuationPolicy`，或新建同样小的 HandFlow 策略；
2. 明确定义 `winner_target`、赢家退出规则、牌山耗尽规则、下一活动玩家规则；
3. 为客户端补充真正需要的 `PresentationProfile` 字段；
4. 为每种流程建立组合测试，覆盖自摸、荣和和多响应。

## 如何给其他规则接入

以“血战到底国标”为例，**不应该**复制 `game_guobiao` 成一套 `game_guobiao_blood_battle`。

推荐的装配目标是：

```text
GuobiaoActionPolicy
+ GuobiaoSettlementPolicy
+ WinContinuationPolicy(third_win)
+ PresentationProfile.for_win_continuation(...)
```

接入步骤：

1. 为国标提取薄的 action adapter 和 settlement adapter；先复用现有国标计算代码，不重写番种。
2. 在规则工厂/状态机构造处创建 `RuleComposition`，仅将 hand flow 换为 `third_win`。
3. 广播同一份 `hand_flow` / `presentation_profile` 协议。
4. Unity 不新增“血战国标”规则名判断，而是复用已有能力查询。
5. 添加组合测试：国标行动与计分保持原样，只有“和牌后退出、轮到谁、何时结束”改变。

如果血战国标的支付规则确实不同，应新增一个国标结算策略或参数；这仍是计分模块的改动，而不是流程模块的分叉。

## 与长沙麻将接入方式的关系

长沙规则已完整打通计算、房间、路由、状态管理、Unity 配置与测试，这是新规则接入完整性的参考。它目前仍复制了较多状态机、等待行动和广播代码。

本架构的方向是保留长沙这种“接入链路完整、测试边界明确”的优点，同时让新增规则尽量只新增动作/计分差异，并复用公共流程与展示协议。长沙无需在本次改造中迁移；未来可逐步把其流程和展示差异接到同一个组合模型。

## 测试与后续工作

当前公共流程测试位于 `server/gamestate/public/test_win_continuation.py`，覆盖三种模式、旧 `blood_battle` 兼容、房间校验、组合装配和广播字段。

下一步推荐按以下顺序继续：

1. 将多响应优先级提炼为独立的响应解析器；
2. 将摸牌、超时、活动玩家推进提炼为公共 hand engine；
3. 将重连、录像、广播 envelope 从 `NewRuleGameState` 迁至公共编排层；
4. 再为国标接入薄 adapter，验证“普通国标 / 血战国标”仅通过装配切换。
