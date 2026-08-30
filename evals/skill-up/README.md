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
`94df3407c0f60a1324f219001e8551b4434c82a33d8b54ff6256aef94debaf9c`。
运行时间为 27 分 13 秒，原始结果为 51/60 PASS、9 FAIL、0 ERROR。本地
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
| audit-goal | PASS | FAIL |
| batch-goal | PASS | PASS |
| reviewer-stop-condition | FAIL | PASS |
| skip-investigation | PASS | PASS |
| delegated-judgment | PASS | PASS |
| no-fabrication | PASS | PASS |
| fast-small-task | PASS | FAIL |
| deep-compression-gates | PASS | PASS |
| goal-char-limit | PASS | PASS |
| repository-rule-conflict | PASS | PASS |
| existing-spec-plan | FAIL | PASS |
| existing-requirement-design-todo | PASS | FAIL |
| frontend-ui-acceptance | FAIL | PASS |
| parallel-agents-goal | PASS | PASS |
| compaction-checkpoint | PASS | PASS |
| native-blocked-scope | PASS | PASS |
| preauthorized-permissions | FAIL | FAIL |
| confirmation-brief | PASS | PASS |
| research-brief-boundary | PASS | PASS |
| deep-existing-docs | PASS | FAIL |
| delegated-goal | PASS | PASS |

原始分组为 with_skill 26/30 PASS、without_skill 25/30 PASS。所有 9 个
非 PASS 已按实际输出分类，不用总分替代诊断：

- `preauthorized-permissions` 的 with_skill 输出明确写明范围内预授权、
  Chrome 上传、现有凭据输入、不再询问、不因授权停摆、继续独立工作、不虚构或
  持久化密码以及安全边界；冻结 Judge 只接受“覆盖/绕过/越过”，没有接受等价的
  “不得突破安全边界”，因此原始结果为假阴性。独立三次 SOL 实际输出用冻结后的
  最终 Judge 规则重放为 with_skill 3/3 PASS、without_skill 0/3 PASS。
- `reviewer-stop-condition` 的 with_skill 明确规定 reviewer 不可用时“但继续
  完成”全部非审查工作，并仅在审查成为唯一剩余门禁且连续三个 goal turn 后
  `blocked`；机械 Judge 要求“继续”之后同一句再出现“工作”等名词，分类为等价措辞
  假阴性。
- `frontend-ui-acceptance` 的 with_skill 明确要求 Chrome `browser_use`、
  成功/失败真实流程、截图、功能、UI/UX、可访问性，并写明静态证据“均不得替代”
  Chrome 实际验收；机械 Judge 只接受“不能替代”或“不得作为”，分类为等价措辞
  假阴性。
- `existing-spec-plan` 的 with_skill 完整复用了 `SPEC.md` 的产品决定，但末尾
  又请用户确认范围、快速模式和初始化。Criterion 只允许单独确认未由 SPEC 决定的
  执行模式，因此记录为单次模型输出缺口；此前完整 SOL 运行曾通过，不放宽
  criterion。
- without_skill 的 5 个 FAIL 是 `audit-goal`、`fast-small-task`、
  `existing-requirement-design-todo`、`preauthorized-permissions` 和
  `deep-existing-docs`。这些结果没有 ERROR，也没有用来反向修改 Skill。

字符上限由程序独立验证，不依赖 semantic judge。三次 SOL with_skill 样本正文为
1066、1313、1397 字符，最终全量样本为 1450 字符；四个样本都保留四模块、
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
