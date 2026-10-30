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
`eval.yaml`; individual cases can override the judge model. Deterministic
`expect` and `script` checks remain the default. Reproducing the historical cohort requires its
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
cohort needs a separate config that replaces both the
execution engine/model and every case-level Agent Judge model with compatible
Claude values. Overriding only `--engine` and `--model` is insufficient.

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

## Deterministic contracts

The reusable structural checker accepts a generated response or a directory of
generated documents:

```bash
EVAL_FINAL_MESSAGE="$(cat generated-goal.md)" \
  evals/skill-up/fixtures/scripts/check-goal-contract.py --profile long

evals/skill-up/fixtures/scripts/check-goal-contract.py \
  --profile long --root .goal-task/example

evals/skill-up/fixtures/scripts/check-goal-char-limit.py \
  --source generated-response.md
```

| Profile | Required evidence |
| --- | --- |
| `long` | Visible progress, milestone commits, completed and remaining work, the next action, and a `state.md` checkpoint before compaction or handoff |
| `parallel` | Lane ownership, one writer for shared schema and lockfiles, integration reruns, and an independent reviewer |
| `ui` | Chrome `browser_use`, successful and failed interactions, browser evidence, UI/UX review, and accessibility review |
| character limit | A rendered goal body shorter than 4000 Unicode characters |

The fixture suite includes passing and intentionally incomplete samples. It
also proves that 3999 characters pass, 4001 fail, and a response without a goal
is rejected.

## Recorded results

The paired cohort used 30 frozen cases, `gpt-5.6-luna` with high reasoning,
Sol semantic judges, `parallelism: 1`, and the isolation requirements above.

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

## Limitations

- This is a Prompt-level evaluation. A generated requirement for code, Chrome,
  CI, migration, or rollback does not prove that the action occurred.
- The paired cohort isolated the target, but it was not a fully hermetic
  operating-system environment. One baseline case listed host metadata without
  reading the target Skill, repository, memories, or prior results.
- Static and semantic judges can still miss valid paraphrases or accept precise
  wording that an execution Agent would not follow.
