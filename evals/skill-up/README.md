# skill-up evaluation

This directory contains the 31-case Prompt-level regression suite for
`goal-prompt`. The smaller `skills/goal-prompt/evals/` set ships with the
Skill.

The suite checks whether an Agent produces the required goal contract. It does
not prove that the generated goal was executed successfully.

## Run the evaluation

Use the [latest skill-up release](https://github.com/alibaba/skill-up/releases/latest)
for new runs. CI is pinned to 0.14.0 with a checked installer and tests its multi-judge and expect-gate behavior without model calls.

Validate the full suite before a run:

```bash
skill-up validate evals/skill-up/eval.yaml
```

The recorded release baseline used `skill-up 0.9.1`, Codex
`gpt-5.6-luna` with high reasoning, and `gpt-5.6-sol` semantic judges.
The execution model and default semantic judge model are specified in
`eval.yaml`; individual cases can override the judge model. The three migrated
cases below explicitly use Luna semantic Judges; list members do not inherit
the singular global Judge defaults. Reproducing the historical cohort requires its
original execution and judge models and the isolation protocol below.

For a new development run, start with no existing target directory so stale
files cannot survive:

```bash
skill-up --version
test ! -e .eval-work/target
mkdir -p .eval-work/target
git archive HEAD:skills/goal-prompt | tar -x -C .eval-work/target
skill-up run evals/skill-up/eval.yaml \
  --output-dir "$(mktemp -d "$PWD/.eval-work/run.XXXXXX")"
```

This command evaluates the Skill at committed `HEAD`; uncommitted Skill changes
are not included. The evaluation config and case files are read from the working
tree. A `--model` override changes the execution model only; semantic judges
use the global judge model unless a case overrides it. Record the actual models
and reasoning effort for the new cohort; the historical scores below do not
measure this configuration. A Claude Code
cohort is explicitly skipped for 1.3; only installation/static compatibility has been checked. A future live cohort needs a separate config that replaces both the
execution engine/model and every case-level Agent Judge model with compatible
Claude values. Overriding only `--engine` and `--model` is insufficient.

## Maintained tools and local archives

Keep reusable evaluation source in this repository; keep generated outputs and
machine state outside the source change. `/.goal-task/`, `.eval-work/`, and
`evals/skill-up/evidence/` are ignored. The small, deliberately authored
`fixtures/` and regression tests remain versioned. Ignoring a directory does not
remove existing evidence from disk; preserve the original configs, outputs,
grades, request ledger and source hashes when sharing a separate run archive.
Do not report an unavailable archive or an unrun case as a pass.

| Entry | Intended use and prerequisites |
| --- | --- |
| `scripts/run-targeted.py`, `summarize-targeted.py` | Start here for new targeted runs. Accept explicit Skill, cases, binary, run and output paths; distinguish natural routing from explicit invocation. |
| `scripts/test-skill-up-upgrade.py` | Credential-free CLI compatibility checks used by CI. |
| `scripts/test-api-broker.py`, `test-business-redaction.py` | Credential-free broker failure and source-label blinding regressions used by CI; loopback HTTP uses synthetic auth and a fake upstream. |
| `scripts/baseline-container/`, `baseline-docker.py`, `without-only.patch` | Reusable, versioned Luna xhigh isolation profile. Build the image and configure the trusted broker/network explicitly; there is no portable one-command launcher. |
| `scripts/audit-*-requests.py`, `audit-request-outcomes.py`, `test-request-outcomes.py` | Reconcile archived native requests and test missing/retry records; not a new model run. |
| `scripts/run-baseline.py`, `run-with-skill.py`, `summarize-baseline.py`, `summarize-paired.py`, `test-audit-discovery.py` | Frozen 30-case Luna profile. Starting a cohort requires its original input revision, patched binary and valid `isolation.json`; with-Skill also requires the matching without archive. |
| `scripts/run-failed-pairs.py`, `run-failed-pairs-resume.py`, `summarize-failed-pairs.py` | Experimental paired comparisons and recovery. Require the frozen before/current bundles, prefix, protocol and existing-run ledger. Recovery continues a verified prefix rather than regenerating successful work. |
| `scripts/replay-paired-judges.py`, `run-script-replay-isolated.py`, `rejudge-business-state.py`, `summarize-luna-calibration.py` | Historical experiment replay. Some sample paths and dependency hashes are fixed; obtain the matching local archive first. In particular, business-state rejudging requires its archived repaired harness. These are not fresh-clone test commands. |

The machine-specific `with-skill-isolation.py` launcher is local and ignored:
its personal auth path, image ID and host proxy are not a supported installation
interface. Future portable launchers need explicit configuration and a separate
validation; do not copy a maintainer's credentials or silently substitute a
model. The versioned container README documents the current profile boundaries.

The optional [native capacity fixture](fixtures/capacity-recovery/README.md)
uses a real disposable Codex host with a scripted local provider and no external
model calls. It checks host transitions and can import an experimental policy
module; it does not certify a Desktop socket client or production auto-recovery.

Result summaries remain public: [6.1 Sol high targeted results](gpt61-refresh.md)
and [Luna xhigh results](../../docs/luna-xhigh-trial.md). They preserve original
versus calibrated grades and the limits of each cohort. Raw JSON, transcripts,
repeated snapshots, incident screenshots and task recovery notes are local
archives rather than repository source. No temporary review-only artifacts are
required by this PR; future exceptions must state their owner and removal gate.

## Frozen targeted runs

The default configuration now runs **with Skill only** (`benchmark.enabled: false`),
collects generated `.goal-task/**/*.md`, and pins Codex 0.164.0 to avoid the
adapter installing its older default. `--baseline` explicitly opts into both
cohorts; use the isolation protocol below before publishing a paired comparison.

For a frozen GPT 6.1 targeted run, use Python 3.10 or newer and install the development-only dependency with
`python3 -m pip install -r evals/skill-up/requirements.txt` in a virtual environment,
and use the checked
skill-up 0.14.0 binary:

```bash
python3 evals/skill-up/scripts/run-targeted.py \
  --skill skills/goal-prompt \
  --invoke-skill \
  --skill-up /path/to/skill-up \
  --output .eval-work/targeted-new \
  --cases research-goal no-fabrication repository-rule-conflict \
    existing-requirement-design-todo preauthorized-permissions confirmation-brief
```

`--invoke-skill` adds one fixed explicit invocation prefix to the first user
turn and retains both original and dispatched inputs. Omit it for a separate
automatic-routing run; never attribute changes in invocation to Skill quality.
For a future with/without comparison, use identical original task inputs in both
cohorts, rather than the explicit target-path prefix used for this behavior trial.

The Skill source must be a self-contained ordinary directory: symbolic links
inside the payload, including internal and broken links, are rejected before
catalog probing or use of the snapshot. This copy policy is not OS isolation.

The output must not already exist. `--prepare-only` freezes and validates without
calling a model. The runner snapshots the Skill, cases, fixtures and effective
config; records hashes, versions, model/reasoning settings and command; and keeps
responses, grading, transcripts and generated state. `--run-prepared --output
<prepared-directory>` verifies the frozen hashes and delegates to the archived
runner if needed; it refuses to overwrite started runs. After an interrupted
run, preserve its evidence and freeze a new output for the remaining cases. It uses the existing Codex
login without copying credentials or changing HOME/CODEX_HOME, disables user
configuration and unrelated features, explicitly disables discovered host Skills,
and uses a fresh case workspace. The initial skip_host_skill_discovery-only runs
were found to retain host catalog entries; their results remain recorded as
contaminated rather than being used as isolated comparisons. This is **not OS isolation** and does not establish a clean
without-Skill baseline. Audit `transcript-audit.json` and the underlying transcripts
for actual Skill/reference reads and observed model/effort.

`host-recovery-boundary` uses the new independent `judges` list: a length check
and a semantic judge assess the same execution. Every member must pass; inspect
`evaluation.json` member verdicts rather than treating the compatibility assertion
average as a case pass rate. Members share files and must remain read-only.
The CI smoke deliberately mutates its fixture to prove that shared-runtime
behavior; it uses a deterministic engine and makes no model calls.

The [GPT 6.1 refresh report](gpt61-refresh.md) separates current targeted results,
measurement repairs and the unchanged historical cohort below. Full 6.1 with-Skill
regression and full without-Skill control remain separate TODOs, not implied passes.

## Full-run follow-up command (not run in this refresh)

After installing the development requirements, this command selects all declared
cases without manually copying their IDs. It uses the checked local binary and
creates a fresh output; `--prepare-only` can be added before `--cases` to validate
and freeze without model calls. This is explicit-invocation with-Skill coverage;
a natural with/without comparison still needs the separate isolation protocol.

```bash
python3 - <<'PYTHON'
from pathlib import Path
import subprocess
import sys
import yaml

config = yaml.safe_load(Path("evals/skill-up/eval.yaml").read_text())
cases = [yaml.safe_load((Path("evals") / item).read_text())["id"]
         for item in config["cases"]["files"]]
subprocess.run([
    sys.executable, "evals/skill-up/scripts/run-targeted.py",
    "--skill", "skills/goal-prompt", "--skill-up", ".eval-work/bin/skill-up",
    "--output", ".eval-work/full-gpt61-with-skill", "--invoke-skill",
    "--cases", *cases,
], check=True)
PYTHON
```

## Isolation requirements

A normal run is useful during development. The recorded A/B result below was a
manually isolated experiment, not the output of a committed one-command runner.
A publishable with-Skill versus without-Skill comparison must satisfy these
conditions:

1. Freeze the repository revision, target Skill, cases, assertions, scripts,
   and judges before either cohort starts.
2. Give each case a fresh `HOME` and `CODEX_HOME`. Reuse that state only for
   turns within the same case.
3. Disable host Skill discovery, memories, apps, plugins, browser and computer
   connectors, goals, multi-agent features, and Skill search.
4. Hide global copies of the target Skill, the source repository, historical
   results, and saved state from the baseline Agent.
5. Keep the execution model, reasoning effort, judges, timeout, retry policy,
   and parallelism identical across both cohorts.
6. Audit every baseline transcript. Reject the cohort if any case reads the
   target Skill or earlier target results.

An operating-system sandbox is preferred because a clean `HOME` alone does not
prevent an Agent from reading known host paths.

## 判分职责与历史重放

`preauthorized-permissions`、`stage2-migration` 和 `compaction-checkpoint`
采用原生多 Judge：已有字符检查器只验证单个非空 `/goal` 及字符上限；
语义 Judge 按原任务要求判断授权、独立工作和报告/检查点含义。所有成员都通过
才算通过。`expect` 只保留必要的命令/入口标识与退出码，避免词面错误让语义评分
整体 SKIP；中文“提交”不再被英文 `commit` 门槛拦截。

语义评分必须检查实际 goal 和必要执行契约，不能根据文件名推断内容。严格对照继续
使用两阶段隔离：原 final 和真实业务 state 进入 fresh、无 Skill 的 J，检查材料完整且
未截断，缺少必要引用产物标为 UNSCORABLE。原生多 Judge 共享运行环境，本身不证明
盲评或 G/J 隔离。语义 Judge 也会误判，须用独立正反例校准并保留逐项证据；
`fixtures/semantic-calibration.yaml` 是合成校准数据，预期标签和解释不得传给 Judge，
校准通过不代表模型行为或长任务执行通过。

CI 的格式、原生评分路由和回执哈希检查不运行真实语义 Judge，也不验证预标注是否正确。
真实校准须另行执行并保留逐项判分。校准回执
`semantic-calibration-receipt.json` 应绑定各案例 criteria、对应 fixture 子集的哈希、
评分引擎及结果摘要，并注明原始证据的归档位置。主Skill与long参考的哈希另绑定已审查的契约对应关系，变动时须复核rubric；它们不是旧Judge的输入记录。哈希一致只证明回执仍对应当前判据，
CI验证必填判分/哈希字段、候选内容哈希及逐项判分一致性；不访问本地原始档案，不核验原始结果/请求哈希的实际内容；回执内部自洽不能代替重新校准，判据变更后不能继续沿用旧的通过结论。当前回执复用未变的授权/压缩各4份R4观测，迁移新4份只有3份与预标一致，明确标为`uncalibrated`；CI通过只表示回执检查通过，未达4/4扩展门槛，后续重判未运行；详见[Luna专项记录](../../docs/luna-xhigh-trial.md#同批pr意见修复与停止点)。

旧的三个案例脚本保留用于历史协议重放，`check-goal-contract.py` 保留为离线历史判分测试；
它们**不作为上述案例的新语义判分依据**。后者没有被当前 case 引用；其进度解析问题
不等于主 30 例被重新判错。
这些正则仍有已知误受/误拒，作为非阻塞的历史工具限制保留；不声明新Judge已验证所有旧反例。离线 `test-judges.sh` 只证明已有词面样例回归。
其他尚未迁移的脚本不在本轮验证范围内，不能推断它们已获得语义可靠性证明。

机械字符检查：

```bash
evals/skill-up/fixtures/scripts/check-goal-char-limit.py \
  --source generated-response.md
```

| 历史检查器 profile | 原词面检查范围（不是语义证明） |
| --- | --- |
| `long` | Visible progress, milestone commits, completed and remaining work, the next action, and a `state.md` checkpoint before compaction or handoff |
| `parallel` | Lane ownership, one writer for shared schema and lockfiles, integration reruns, and an independent reviewer |
| `ui` | Chrome `browser_use`, successful and failed interactions, browser evidence, UI/UX review, and accessibility review |
| character limit | A rendered goal body shorter than 4000 Unicode characters |

历史重放使用冻结的 case 和 checker，不将新 rubric 套入旧汇总。新语义评分另列协议版本，
保留原始 PASS/FAIL/SKIP/ERROR、输出和必要产物。迁移不会追改历史成绩，也不证明 Skill 提升。

## Recorded results

The paired cohort used 30 frozen cases, `gpt-5.6-luna` with high reasoning,
Sol semantic judges, `parallelism: 1`, and the isolation requirements above.
The totals below retain that historical grading protocol, including deterministic
checkers now marked legacy. They are not full-cohort results under the current
semantic criteria; targeted semantic rejudges are recorded separately.

| Cohort | PASS | FAIL | ERROR |
| --- | ---: | ---: | ---: |
| Luna with Skill | 24 | 6 | 0 |
| Luna without Skill | 6 | 23 | 1 |
| Sol high with Skill | 28 | 2 | 0 |

The Luna pair contains 19 Skill-only passes, one baseline-only pass, five
shared passes, and five shared non-passes. The baseline
`frontend-ui-acceptance` case timed out twice and remains an ERROR.

The original frozen responses were replayed after the deterministic judges were
strengthened. Three former baseline passes were reclassified because their
required contract appeared outside the rendered goal or no rendered goal was
present; no Agent was rerun for this correction.

The final operation-target wording was added after this cohort. Its single
target, ambiguous target, and delegated-choice branches are covered by the
packaged basic evals, but these aggregate scores are not a full rerun of that
last wording change.

| Case | with Skill | without Skill |
| --- | --- | --- |
| audit-goal | PASS | FAIL |
| batch-goal | PASS | FAIL |
| compaction-checkpoint | PASS | FAIL |
| confirmation-brief | FAIL | FAIL |
| deep-compression-gates | PASS | FAIL |
| deep-existing-docs | PASS | FAIL |
| delegated-goal | PASS | FAIL |
| delegated-judgment | PASS | FAIL |
| existing-requirement-design-todo | FAIL | FAIL |
| existing-spec-plan | PASS | PASS |
| fast-small-task | PASS | FAIL |
| frontend-ui-acceptance | PASS | ERROR |
| goal-char-limit | PASS | FAIL |
| multiturn-confirmation | PASS | FAIL |
| multiturn-correction | PASS | FAIL |
| native-blocked-scope | PASS | PASS |
| no-fabrication | FAIL | FAIL |
| parallel-agents-goal | PASS | FAIL |
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

The six Luna with-Skill failures were retained without weakening a case,
assertion, or judge:

| Case | Observed gap |
| --- | --- |
| `research-goal` | Did not fully connect the research scope to the architecture decision and evidence boundary |
| `no-fabrication` | Listed unknowns honestly but did not close with a bounded result and confirmation request |
| `repository-rule-conflict` | Did not cite `REPOSITORY_POLICY.md` explicitly |
| `existing-requirement-design-todo` | Reused the approved documents but underspecified recovery, independent work, and milestone review |
| `preauthorized-permissions` | Generated a goal but missed part of the explicit preauthorization contract |
| `confirmation-brief` | The transcript triggered the premature-final-goal check |

The Sol high result measures with-Skill behavior across execution models. It is
not part of the paired Luna delta. A former Sol without-Skill result was discarded
after 23 of 30 transcripts accessed the host copy of `goal-prompt`.

The separate [GPT-6 Luna xhigh without-Skill control](luna-xhigh-control.md)
completed the original 30 cases with raw results of 6 PASS, 24 FAIL, and 0 ERROR.
Its report retains the original grades and all excluded infrastructure attempts.
The subsequent [GPT-6 Luna xhigh paired run](luna-with-skill-paired.md) completed
the same 30 with-Skill cases: raw 22 PASS / 8 FAIL, or 25 / 5 after deterministic
replay of confirmed judge errors. The existing without outputs calibrate to 7 / 23;
the without model group was not rerun. Both execution and semantic judges used
GPT-6 Luna xhigh. Different judges, effort, tooling, and isolation prevent pooling
these results with the historical 5.6 cohort. The report also separates natural
Skill availability from explicit-invocation before/current failure diagnosis.

## Limitations

- This is a Prompt-level evaluation. A generated requirement for code, Chrome,
  CI, migration, or rollback does not prove that the action occurred.
- The paired cohort isolated the target, but it was not a fully hermetic
  operating-system environment. One baseline case listed host metadata without
  reading the target Skill, repository, memories, or prior results.
- Static and semantic judges can still miss valid paraphrases or accept precise
  wording that an execution Agent would not follow.
