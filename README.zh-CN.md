# goal-prompt

> [English Version](README.md)

`goal-prompt` 用来生成长度合适、边界清楚、可以验证结果的 `/goal`。它会先了解任务和仓库，再提问、等你确认，最后输出可直接复制的提示词。

它不执行任务，也不要求先搭一整套 SPEC。

![goal-prompt 如何解决常见的 /goal 问题](http://img.tingtattoo.cn/goal-prompt-overview-zh.png)

## 为什么需要它

自己写 `/goal` 时，最难拿捏的是尺度。写短了，Agent 做到一半就认为已经完成；写长了，背景、计划和例外全挤在一起，执行时反而容易跑偏。

| 常见做法 | 实际问题 | goal-prompt 的处理 |
| --- | --- | --- |
| 直接手写 `/goal` | 内容忽多忽少，范围和完成条件容易漏 | 保持精炼，优先保留结果、范围、完成门槛和必要执行语义 |
| 只参考 Codex 或 Claude Code 官方说明 | 官方文档解释了命令和基础规则，但不会结合具体仓库判断范围、风险和验证方式 | 先调查真实上下文，再决定目标里该留什么 |
| 使用较早或较重的社区方案 | 有的没有跟上 `/goal` 的变化；有的依赖多份 SPEC，准备时间很长 | 默认不创建额外文件，复杂任务也从一份最小状态开始 |
| 一次生成后直接执行 | 错误假设会原样进入长任务 | 先规划、提问和确认，再生成最终 `/goal` |
| 绑定单一 Agent | 换到其他 Agent 后，调用方式、目录或术语对不上 | 核心指令保持通用，只对平台入口做少量适配 |

长任务还有一个常见问题：这一轮踩过的坑通常只留在聊天记录里，下一轮又要重新摸索。这个 skill 可以在每轮或阶段结束时简单归纳已经证实的经验，不强制维护庞大的知识库。以后如果要写入 Memory，仍需用户单独确认。

## 工作方式

```text
真实任务
   ↓
调查仓库、约束和现状
   ↓
提出会改变目标的问题
   ↓
用户确认目标摘要
   ↓
生成 /goal
   ↓
执行迭代 → 简单归纳有效经验（可选）
```

**第一阶段**只返回临时目标摘要，包括预期结果、范围、排除项和完成证据。会改变目标的假设没有确认前，不会生成 `/goal`。

确认后才进入**第二阶段**。最终提示词只保留执行需要的内容：

- 预期结果、范围和排除项；
- 必须全部满足的完成条件和验证证据；
- 遇到 CI、测试或外部依赖阻塞时如何调整顺序；
- 全部剩余工作确实无法继续时，允许停止的条件；
- 行为变更代码所需的独立审查。

普通任务默认不创建额外文件。需要跨会话恢复时，优先使用一份 `.goal-task/<task-slug>/state.md`，而不是同时维护 `plan.md`、`todo.md`、`progress.md` 和 `lessons.md`。

任务确实很重，而且这四类信息需要分开维护时，可以按职责拆开：

- `plan.md`：记录整体方案、阶段划分和依赖关系，避免执行方向反复变化；
- `todo.md`：维护当前待办、优先级和状态，适合频繁更新；
- `progress.md`：记录已完成内容、验证证据、阻塞和恢复位置，方便跨会话接续；
- `lessons.md`：归纳已经证实的经验、失败假设和有效做法，供后续迭代复用。

如果这些内容由同一个执行者维护、更新节奏也相近，合并到 `state.md` 更省事。

## 安装

安装到 Codex 和 Claude Code：

```bash
npx skills add imbajin/goal-prompt -g -a codex -a claude-code
```

也可以让 Codex 安装：

```text
$skill-installer 将 https://github.com/imbajin/goal-prompt 仓库根目录安装为 goal-prompt
```

其他 Agent 可以运行下面的命令，再选择目标平台：

```bash
npx skills add imbajin/goal-prompt
```

## 使用

```text
# Codex/CC
/goal-prompt 帮我给当前目录的认证模块定一个任务计划, 参考 XX 设计实现
```

请求匹配时，Agent 可以自动调用这个 skill，你也可以手动调用。无论哪种方式，它只生成提示词，不会直接启动 `/goal`。

## 兼容范围

核心内容使用通用的 [Agent Skills](https://agentskills.io/) 目录结构。Codex 通过 `agents/openai.yaml` 提供入口信息，Claude Code 使用标准 skill frontmatter；两者都允许自动选择和手动调用。

请在支持 `/goal` 的版本和会话中使用。Claude Code 需要 v2.1.139 或更高版本。其他 Agent 如果支持 Agent Skills 和类似的 goal 模式，可以直接复用；如果没有原生 `/goal`，仍可生成结构化目标文本，但不会获得持续执行能力。

## 开发与校验

```bash
npx skills@1.5.20 add . --list
```

来源和设计取舍见 [`references/fusion-notes.md`](references/fusion-notes.md)。

## 许可证

Apache License 2.0，详见 [`LICENSE`](LICENSE)。
