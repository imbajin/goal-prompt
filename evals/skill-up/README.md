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

The command above is suitable for a normal with-Skill run. A publishable paired
run needs an additional isolation gate:

1. Freeze the repository commit, target Skill, cases, assertions, scripts, and
   judges before either cohort starts.
2. Give every case a fresh HOME and CODEX_HOME. Provision only the authentication
   material required by the runner.
3. Disable host Skill discovery, memories, apps, plugins, browser/computer
   connectors, goals, multi-agent features, and Skill search.
4. Hide global copies of the target Skill, the source repository, old results,
   and historical state from the baseline Agent. An OS sandbox is preferred.
5. Run both cohorts with the same execution model, reasoning effort, judges,
   timeout, retry policy, and parallelism.
6. Audit every baseline transcript. Reject the cohort if any case reads the
   target Skill or historical target results.

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

### Current Luna paired cohort

发布回归使用 `skill-up 0.9.1`、Codex `gpt-5.6-luna` high
execution agent、SOL semantic judges、`parallelism 1` 和绝对 output
directory。两轮固定使用同一份 Skill、30 个 case、断言、脚本和 Judge。

两轮使用独立的逐 case HOME 和 CODEX_HOME，并关闭宿主 Skill 自动发现、记忆、
apps、plugins、browser/computer connectors、goals、multi-agent 和 Skill search。
运行期间还移走了 `goal-prompt` 的两个常规全局安装，外层 macOS sandbox 禁止读取
仓库、目标 Skill 路径、历史评测目录和记忆文件。with Skill 只安装 case workspace
内的目标副本。

结果为 with Skill 24/30 PASS、without Skill 9/30 PASS。baseline 的
`frontend-ui-acceptance` 两次达到 420 秒上限，原样保留为 ERROR。配对后有
16 个 Skill-only PASS、1 个 baseline-only PASS、8 个共同 PASS 和 5 个共同
non-PASS。

| Case | with Skill | without Skill |
| --- | --- | --- |
| audit-goal | PASS | FAIL |
| batch-goal | PASS | FAIL |
| compaction-checkpoint | PASS | FAIL |
| confirmation-brief | FAIL | FAIL |
| deep-compression-gates | PASS | FAIL |
| deep-existing-docs | PASS | PASS |
| delegated-goal | PASS | FAIL |
| delegated-judgment | PASS | FAIL |
| existing-requirement-design-todo | FAIL | FAIL |
| existing-spec-plan | PASS | PASS |
| fast-small-task | PASS | FAIL |
| frontend-ui-acceptance | PASS | ERROR |
| goal-char-limit | PASS | PASS |
| multiturn-confirmation | PASS | FAIL |
| multiturn-correction | PASS | FAIL |
| native-blocked-scope | PASS | PASS |
| no-fabrication | FAIL | FAIL |
| parallel-agents-goal | PASS | PASS |
| preauthorized-permissions | FAIL | FAIL |
| repository-rule-conflict | FAIL | FAIL |
| research-brief-boundary | PASS | FAIL |
| research-goal | FAIL | PASS |
| reviewer-stop-condition | PASS | FAIL |
| skip-investigation | PASS | PASS |
| stage1-grounded-feature | PASS | FAIL |
| stage1-long-running | PASS | FAIL |
| stage1-vague-draft | PASS | FAIL |
| stage2-doc | PASS | PASS |
| stage2-migration | PASS | FAIL |
| trigger-boundary | PASS | PASS |

with Skill 的 6 个 FAIL 原样保留，没有修改 case、放宽断言或重跑到通过。

- `research-goal` 没有完整写清研究所支持的架构决策和证据边界。
- `no-fabrication` 诚实列出了未知项，但没有形成有限结果和请求确认的闭环。
- `repository-rule-conflict` 没有显式引用 fixture 中的
  `REPOSITORY_POLICY.md`。
- `existing-requirement-design-todo` 复用了三份定稿文档，但恢复入口、
  独立工作重排和重大里程碑 review 仍不够具体。
- `preauthorized-permissions` 生成了目标，但没有满足预授权脚本的完整措辞契约。
- `confirmation-brief` 的最终回复停在调查和补充问题；完整 transcript 仍触发了
  premature-final-goal 检查。

隔离审计还记录了一处宿主元数据可见。baseline 的
`reviewer-stop-condition` 枚举了宿主 `.codex` 元数据和无关全局 Skill 名称。
它还检查了常规 `goal-prompt/SKILL.md` 路径。目标安装当时已移走，命令输出没有
该路径或目标内容，transcript 也没有成功读取仓库、历史结果或记忆正文。因此这轮
可称为目标隔离的对照评测，不称作完全 hermetic 的操作系统环境。

原始 JSON、HTML、transcript、Judge context、grading evidence、逐 case HOME
映射和脱敏配置保存在本地
`.eval-work/luna-isolated-20260831-final/`。凭据与 Codex 状态数据库不在该目录。

### with-Skill across execution models

with Skill 在 `gpt-5.6-sol` 下为 28/30 PASS、2 FAIL、0 ERROR。这组结果用于
观察 execution model 对 Skill 表现的影响。严格的 with/without 差值仍以 Luna
同环境配对为准。此前记录的 SOL without-Skill 26/30 在审计中发现 23/30
transcript 读取了宿主
`goal-prompt`，已从有效对照中撤下，不再用于 README 结论。没有为了补齐 SOL
对照再跑一轮，避免不必要的模型开销。

这仍是 Prompt-level 评测。静态 Judge、目标文本和浏览器验收条款不能证明真实代码、
Chrome、CI、迁移或回滚已经执行。
