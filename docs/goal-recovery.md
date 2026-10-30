# Capacity 与 Goal 恢复边界

1.3没有实现capacity自动恢复。Skill能保存检查点和恢复证据；请求重试、Goal状态迁移和重新激活由宿主控制。本文不依赖某个用户聊天或私有日志。

2026-10-30核对Codex公开main的固定快照；下列关键文件与此前核对版本一致。源码可解释机制，但不证明所有已安装二进制都有相同行为。

| 层次 | 当前核对到的行为 |
| --- | --- |
| 请求重试 | `ServerOverloaded`使用服务器提供的重试延迟；没有提示时不会像一般连接错误那样使用本地默认退避。重试仍受控制器限制。 |
| 错误终止 | 回合以不可重试或重试耗尽的错误结束后，Goal错误钩子把非额度错误归为`TurnError`，持久化为`Blocked`，阻止失败续跑循环。 |
| 自动接续 | 仅接续`Active`的Goal；已经`Blocked`不会仅因容量稍后恢复而自动重新激活。 |
| 恢复权限 | Agent的`update_goal`不能把状态改为`active`；恢复由用户或系统控制。 |

请求层依据[错误分类](https://github.com/openai/codex/blob/f2ac9983552d187aa1c9a53c4707cf3b2c4afde6/codex-rs/protocol/src/error.rs#L421-L470)和[重试控制](https://github.com/openai/codex/blob/f2ac9983552d187aa1c9a53c4707cf3b2c4afde6/codex-rs/core/src/responses_retry.rs#L88-L103)；Goal层依据[错误钩子](https://github.com/openai/codex/blob/f2ac9983552d187aa1c9a53c4707cf3b2c4afde6/codex-rs/ext/goal/src/extension.rs#L423-L447)、[停止映射](https://github.com/openai/codex/blob/f2ac9983552d187aa1c9a53c4707cf3b2c4afde6/codex-rs/ext/goal/src/runtime.rs#L315-L318)、[接续条件](https://github.com/openai/codex/blob/f2ac9983552d187aa1c9a53c4707cf3b2c4afde6/codex-rs/ext/goal/src/runtime.rs#L465-L479)和[工具权限](https://github.com/openai/codex/blob/f2ac9983552d187aa1c9a53c4707cf3b2c4afde6/codex-rs/ext/goal/src/tool.rs#L246-L259)。

因此，实际路径可能是：请求重试 → 终态capacity错误 → 宿主写入`blocked` → 等待用户/系统恢复同一Goal。模型主动标blocked所需的多轮审计不能覆盖这个宿主错误钩子；宿主blocked也不同于用户主动暂停。

Skill目前能做的是在重要派发前记录已验证结果、未完成门槛、后台run句柄和不可重派账本；恢复后先核查状态、进程及已生成输出，再继续独立工作。模型已经无法采样时，不能指望它在失败后补写检查点。

没有新增定时唤醒器、自动resume或静默切换模型。恢复入口应按当前宿主核实；不要假设报错处的“重试”必然重新激活Goal。[官方Goal说明](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)也将恢复权限保留给用户/系统。今后若增加自动恢复，需要另外验证调度权限、有限退避、取消和幂等性，尤其要避免重复派发未知状态的请求。
