# skill-up evaluation

This directory contains the reproducible Prompt-level regression suite. The
smaller `skills/goal-prompt/evals/` set ships with the Skill.

## Validate

This checks definitions only. It does not run an Agent or prove behavior.

```bash
skill-up validate evals/skill-up/eval.yaml
```

## Run

Run from the repository root. All snapshots, isolated HOME data, and results
stay under `.eval-work/`.

The suite pins the execution agent to `gpt-5.6-luna`. Use Codex reasoning
effort `high` for full runs. Escalate only failed or flaky cases to `xhigh` for
targeted reruns. Keep deterministic `expect` and `script` checks as the default;
use `gpt-5.6-sol` only for cases that require semantic judging, not as the
long-running execution agent.

```bash
commit="$(git rev-parse HEAD)"
workdir="$PWD/.eval-work/$commit"
target="$PWD/.eval-work/target"
codex_home="${CODEX_HOME:-$HOME/.codex}"

mkdir -p "$target" "$workdir/home" "$workdir/results"
git archive "$commit:skills/goal-prompt" | tar -x -C "$target"

test -f "$target/SKILL.md"
skill-up validate "$PWD/evals/skill-up/eval.yaml"

HOME="$workdir/home" CODEX_HOME="$codex_home" \
skill-up run "$PWD/evals/skill-up/eval.yaml" \
  --output-dir "$workdir/results"
```

Use `--dry-run` to inspect the selected cases without running them. A real run
uses the configured Agent and judge, so local login or credentials must already
work.

Generating `/goal` proves only the Prompt layer. End-to-end task completion
requires a separate execution evaluation.

## Deterministic execution-contract checks

The cases for long-running, parallel, and UI work use self-contained structural
judge scripts with the same contract. The reusable
`fixtures/scripts/check-goal-contract.py` checker is also available for local
checks and generated-document directories. It is deliberately a structural
gate: it fails when the generated goal does not explicitly name the required
contract, and it does not claim that the named work was actually executed.

```bash
EVAL_FINAL_MESSAGE="$(cat generated-goal.md)" \
  evals/skill-up/fixtures/scripts/check-goal-contract.py --profile long

evals/skill-up/fixtures/scripts/check-goal-contract.py \
  --profile long --root .goal-task/example
```

`long` requires a visible progress bar/percentage, milestone commit, current
completed-item summary, compaction or handoff checkpoint in `state.md`, and
remaining/next work. `parallel` requires lane ownership, a single owner for
shared schema or lockfile, integration re-run, and an independent reviewer.
`ui` requires Chrome `browser_use`, real success/failure interaction, browser
evidence, separate UI/UX and accessibility checks, and an explicit statement
that static checks do not replace browser acceptance. The fixture tests include
both passing and intentionally incomplete Markdown documents.

## Evaluation summary

本轮把评测分成两层。24 个既有 case 加 4 个新增 case，共 28 个 case；既有
case 用同一批输入分别运行 with_skill 和 without_skill，结果保存在本地运行证据中，
这些证据不随仓库提交。这是修改前的可落盘基线，作用是保留完整对照，不把一次波动
误报成改进。

| Case | with_skill | without_skill |
| --- | --- | --- |
| stage1-grounded-feature | FAIL | FAIL |
| stage1-vague-draft | FAIL | FAIL |
| stage1-long-running | PASS | FAIL |
| stage2-doc | PASS | PASS |
| stage2-migration | FAIL | FAIL |
| multiturn-confirmation | PASS | ERROR |
| multiturn-correction | FAIL | ERROR |
| trigger-boundary | PASS | PASS |
| research-goal | FAIL | FAIL |
| audit-goal | FAIL | FAIL |
| batch-goal | PASS | FAIL |
| reviewer-stop-condition | FAIL | FAIL |
| skip-investigation | PASS | PASS |
| delegated-judgment | FAIL | ERROR |
| no-fabrication | PASS | FAIL |
| fast-small-task | PASS | FAIL |
| deep-compression-gates | PASS | FAIL |
| repository-rule-conflict | FAIL | FAIL |
| existing-spec-plan | PASS | PASS |
| existing-requirement-design-todo | FAIL | FAIL |
| frontend-ui-acceptance | PASS | PASS |
| parallel-agents-goal | FAIL | FAIL |
| compaction-checkpoint | FAIL | FAIL |
| native-blocked-scope | PASS | PASS |

基线合计为 with_skill 12/24 PASS、without_skill 6/24 PASS，另有
without_skill 3 个 ERROR。FAIL 里既有真实行为缺口，也有判定脚本对等价措辞过窄的情况，
所以只看总数不能替代逐 case 解释。

本轮新增 4 个回归 case，均对应之前的具体缺口。

| 新 case | 检查意义 |
| --- | --- |
| confirmation-brief | 未确认时只给调查 brief，不能因为资料足够就提前输出最终目标 |
| research-brief-boundary | 只读研究要分开证据缺口和偏好缺口，不能机械加入实现 reviewer 门槛 |
| deep-existing-docs | 已有 requirement、design、todo 且已确认 deep 时，仍保留 state、恢复、重排和三名 reviewer |
| delegated-goal | 用户委托剩余判断后继续生成诚实目标，缺少仓库事实要保留为未知，不能停在索要路径 |

新增 case 的 with_skill 实际输出在 Luna high 下经修正后的判定器复核为 4/4。首次运行中
`research-brief-boundary` 被判定脚本误报，因为输出明确写了“行为变更 reviewer 不应作为默认门槛”，
脚本却把“门槛”关键词当成正向要求。脚本随后改为识别正向强制语义，并加入否定语境回归，
用同一份实际输出重跑通过。这个调整只修正判定器的语义等价误判，没有放宽 case 要求。

当前 prompt 的改动集中在四个边界。第一，增加显式路由门，首轮 brief、确认、委托判断和明确跳过分别进入确定状态，避免首轮泄漏最终目标。第二，明确“跳过调查并跳过确认”可以直接进入 Stage 2，同时保留未知事实；只说“直接生成”仍要读取可用仓库资料。第三，复杂度、跨会话恢复、迁移兼容和多子系统任务保守推荐 deep，已有 truth 文档不会让任务降级。第四，研究和审计 brief 保持只读，代码 reviewer 只在用户要求 remediation 或证据明确需要时出现。

判定器还补充了等价表达，例如“可继续”“不依赖”“独立推进”和
“不应作为默认门槛”。这些变化不改变 case 的目标，只避免把同一语义的中文表达误判为失败。

24 个历史 case 的最新全量重跑曾受到 skill-up/Codex 运行器错误影响，日志出现
`invalid value ... expected i32` 以及 rollout thread flush 失败，未生成可信的完整 result.json。
因此 README 保留上面的落盘基线，并单独报告新增回归结果，不用不完整日志冒充新的 24-case 总分。
