# Capacity 与 Goal 恢复边界

1.3仅引入恢复边界说明、检查点要求和可复跑故障注入测试；正式Skill包未提供或启用capacity自动恢复脚本。实验策略核心仅作为仓库测试fixture维护，不能直接连接Desktop。Skill能保存检查点和恢复证据；请求重试、Goal状态迁移和重新激活由宿主控制。本文不依赖某个用户聊天或私有日志。

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

## 小规模故障注入实测

已用真实Codex 0.164.0宿主和本地策略原型做三项集成验证。每项在新Docker容器运行，禁止外连、无宿主挂载或已有凭据；Responses由容器内loopback脚本服务提供。Luna/xhigh是请求配置标签，没有外部模型调用，也没有制造或观察线上capacity事故。

| 场景 | 实际观测 |
| --- | --- |
| capacity终态 | 原型提前在宿主外运行，Goal阻塞后仍存活；配置等待0.25秒，实际约0.263秒，唯一激活原Goal并触发新回合成功。目标、预算及容器内原生Goal ID保持。 |
| 等待期用户暂停 | 真实Goal保持paused，恢复写入0次。 |
| 非capacity额度错误 | 真实Goal为usageLimited，恢复写入0次。 |

0.25秒是加速验证计时与控制流，不表示实测过5分钟线上中断。策略原型支持初始退避、最大退避、抖动、次数和总时限配置；按本次用户要求，新原型默认三次重试分别等待5→15→30分钟，最多3次、总时限60分钟，默认不加抖动但可配置启用。新默认值已通过零模型虚拟时钟验证，三档为300/900/1800秒、合计3000秒；没有据此重跑或改写上面的0.25秒原生记录。它必须在active阶段预先armed，核对对应的终态失败、配置、排队输入及等待期变更；既有blocked原因不明时不自动恢复。

离线策略检查另覆盖暂停、模型配置变化、丢回执、重复恢复和预算上限，并故意复现最终GET→SET暂停竞态。该反例未算作安全通过；原子条件恢复仍需宿主支持。当前终态RPC没有结构化Retry-After，原型只按配置或显式可信等待下限退避，不能宣称自动读到服务端等待提示。

可复跑入口见[原生故障注入fixture](../evals/skill-up/fixtures/capacity-recovery/README.md)。R1后将已测策略核心整理为[实验测试模块](../evals/skill-up/fixtures/capacity-recovery/retry_policy.py)，移除不可用的socket CLI；正例、暂停和额度三场景现在均可直接使用仓库源码复跑，R1已在同一隔离profile下再次通过（零外部模型调用）。新模块默认5/15/30分钟经18项离线检查，其中一项刻意暴露未解决竞态，不作为安全证明。逐条RPC、原始失败和运行配置仍在本地忽略目录，新运行位于`.eval-work/pr-review-r1-20261031/native-*`，旧冻结源与旧结果保留。

**仍未验证：**正式独立脚本的Desktop接入、从Skill执行阶段启动后的完整生命周期、线上capacity恢复和原子并发保护。已证明`app-server proxy --sock`只是原始字节relay，不能直接替代Unix socket的WebSocket握手；stdio策略集成不等于socket命令行端到端成功。本次没有把原型安装进Skill，也没有改变默认生成流程或操作现有业务聊天。
