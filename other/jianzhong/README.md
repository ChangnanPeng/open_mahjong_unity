# 简中麻将（Jianzhong）

`jianzhong` 是“简化版中庸麻将规则”的正式规则标识。本目录只保留生产 review 所需的规则、架构与计分说明；历史计划、试玩快照和 Debug 场景保留在旧开发分支，不进入 production 分支。

## 文档

- [规则定义](rule_reference.md)
- [可组合架构](architecture.md)
- [番种与计分](fan_scoring.md)

## 代码入口

服务端：

- `server/game_calculation/jianzhong`：牌型分解、番种、计分和听牌。
- `server/gamestate/game_jianzhong`：简中动作、结算、广播和对局编排。
- `server/gamestate/public/rule_composition.py`：动作、计分、终局流程和展示能力的组合。
- `server/database/jianzhong`：基于公共牌谱表的持久化适配。

Unity：

- `JianzhongExternal`：与其他规则并列的客户端听牌计算入口。
- `NormalGameStateManager.RuleCapabilities`：消费服务端声明的流程和展示能力。
- `Jianzhong_Create_RoomConfig`：简中建房配置。

## Review 原则

- Python 服务端是合法动作、计分和结算的权威来源。
- Unity 只在需要即时交互时本地计算听牌形状。
- 新增能力应优先扩展公共组合协议，而不是添加规则名特判。
- `jianzhong` 没有需要兼容的旧协议名；代码和文档只使用正式名称。
