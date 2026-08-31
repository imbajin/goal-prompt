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

The committed suite pins the execution agent to `gpt-5.6-luna`. Use
`skill-up 0.9.1` or later and Codex reasoning effort `high` for full runs.
Escalate only failed or flaky cases to `xhigh` for targeted reruns. Keep
deterministic `expect` and `script` checks as the default; use
`gpt-5.6-sol` for semantic judges. A controlled SOL execution cohort may use
`--model gpt-5.6-sol`, but report it separately and do not silently replace the
committed Luna baseline.

```bash
commit="$(git rev-parse HEAD)"
workdir="$PWD/.eval-work/$commit"
target="$PWD/.eval-work/target"
codex_home="${CODEX_HOME:-$HOME/.codex}"

mkdir -p "$target" "$workdir/home" "$workdir/results"
git archive "$commit:skills/goal-prompt" | tar -x -C "$target"

test -f "$target/SKILL.md"
test "$(skill-up --version)" = "skill-up version 0.9.1"
skill-up validate "$PWD/evals/skill-up/eval.yaml"

HOME="$workdir/home" CODEX_HOME="$codex_home" \
skill-up run "$PWD/evals/skill-up/eval.yaml" \
  --output-dir "$workdir/results"
```

Use `--dry-run` to inspect the selected cases without running them. A real run
uses the configured Agent and judge, so local login or credentials must already
work. Keep `--output-dir` absolute. With a relative output directory,
`skill-up 0.9.1` can reject agent-judge materials such as `final_message.txt` as
escaping the Judge context directory.

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

evals/skill-up/fixtures/scripts/check-goal-char-limit.py \
  --source generated-response.md
```

`long` requires a visible progress bar/percentage, milestone commit, current
completed-item summary, compaction or handoff checkpoint in `state.md`, and
remaining/next work. `parallel` requires lane ownership, a single owner for
shared schema or lockfile, integration re-run, and an independent reviewer.
`ui` requires Chrome `browser_use`, real success/failure interaction, browser
evidence, separate UI/UX and accessibility checks, and an explicit statement
that static checks do not replace browser acceptance. The fixture tests include
both passing and intentionally incomplete Markdown documents. The character
checker counts the rendered goal body as Unicode characters and requires fewer
than 4000; fixtures prove 3999 passes, 4001 fails, and a missing goal is rejected.

## Evaluation summary

### Current SOL cohort

2026-08-31 的最终回归使用官方 `skill-up 0.9.1`、Codex
`gpt-5.6-sol` execution agent、SOL semantic judges、`parallelism 4` 和绝对
output directory，对冻结后的 30 个 case 执行同输入的 with_skill /
without_skill 对照。Skill hash 为
`c7f15395c10ade04700307daf0eb687fa19249f9e3f9e98d6886e75a552b4ac9`，
评测输入 hash 为
`285aa531c2bb0a21586e3eadc704a031ea30c3342d945843ad99122e3d31127e`。
运行时间为 35 分 20 秒，原始结果为 54/60 PASS、6 FAIL、0 ERROR。本地
JSON、HTML、transcript、Judge context 和 grading evidence 不提交到仓库。

| Case | with_skill | without_skill |
| --- | --- | --- |
| stage1-grounded-feature | PASS | PASS |
| stage1-vague-draft | PASS | PASS |
| stage1-long-running | PASS | PASS |
| stage2-doc | PASS | PASS |
| stage2-migration | PASS | PASS |
| multiturn-confirmation | PASS | PASS |
| multiturn-correction | PASS | PASS |
| trigger-boundary | PASS | PASS |
| research-goal | PASS | PASS |
| audit-goal | PASS | PASS |
| batch-goal | PASS | PASS |
| reviewer-stop-condition | PASS | PASS |
| skip-investigation | PASS | PASS |
| delegated-judgment | PASS | PASS |
| no-fabrication | PASS | PASS |
| fast-small-task | PASS | PASS |
| deep-compression-gates | PASS | PASS |
| goal-char-limit | PASS | PASS |
| repository-rule-conflict | PASS | PASS |
| existing-spec-plan | PASS | FAIL |
| existing-requirement-design-todo | FAIL | PASS |
| frontend-ui-acceptance | PASS | PASS |
| parallel-agents-goal | PASS | FAIL |
| compaction-checkpoint | PASS | PASS |
| native-blocked-scope | PASS | FAIL |
| preauthorized-permissions | PASS | FAIL |
| confirmation-brief | PASS | PASS |
| research-brief-boundary | FAIL | PASS |
| deep-existing-docs | PASS | PASS |
| delegated-goal | PASS | PASS |

原始分组为 with_skill 28/30 PASS、without_skill 26/30 PASS。所有 6 个
非 PASS 已按实际输出分类，不用总分替代诊断：

- `preauthorized-permissions` 的 with_skill 通过，明确覆盖范围内预授权、
  Chrome 上传、输入已有凭据、Git/push/PR/测试/review、不再询问、不因授权停摆、
  继续独立工作、不虚构凭据或能力、不覆盖安全边界，以及凭据不进入日志、截图、
  提交或 PR。without_skill 未满足完整权限与凭据保护契约，按预期 FAIL。
- `existing-requirement-design-todo` 的 with_skill 复用了三份定稿文档并选择
  deep mode，但只笼统说明等待时继续独立工作，没有列出可重排的具体实现/恢复测试/
  重放覆盖/原因码回归，也只要求最终变更 3 reviewer，未明确每个重大里程碑；
  记录为本轮模型输出缺口，不放宽 criterion。
- `research-brief-boundary` 的 with_skill 已分离证据缺口与偏好缺口，也说明行为
  变化 reviewer 不是默认门槛，但没有显式写出“不修改代码”，记录为模型输出缺口。
- without_skill 的另外三个 FAIL 是 `existing-spec-plan`、
  `parallel-agents-goal` 和 `native-blocked-scope`：分别重新询问 SPEC 已决定的
  范围/验收、未满足共享文件单 owner 契约，以及未满足三轮整体 blocked audit。
  所有结果均无 ERROR。

字符上限由程序独立验证，不依赖 semantic judge。三次 SOL with_skill 样本正文为
1066、1313、1397 字符，最终全量样本为 1468 字符；四个样本都保留四模块、
12 项子门槛、CI、安全审查、5 名 reviewer、修复后复审、迁移文档、运维手册、
四阶段灰度和每阶段回退条件。

### Historical Luna cohort

此前 Luna high 基线包含 24 个 case，with_skill 为 12/24 PASS，
without_skill 为 6/24 PASS，without_skill 另有 3 个运行器 ERROR。随后新增的
`confirmation-brief`、`research-brief-boundary`、`deep-existing-docs` 和
`delegated-goal` 在修正机械等价词后的 Luna 复核为 with_skill 4/4 PASS。
历史 Luna 结果使用旧版 suite 和运行器，只用于保留模型 cohort 的演进背景，不能与
当前 30-case SOL 分数直接合并或当作发布候选结果。

这仍是 Prompt-level 评测。静态 Judge、目标文本和浏览器验收条款不能证明真实代码、
Chrome、CI、迁移或回滚已经执行。
