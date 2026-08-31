# skill-up evaluation

This directory contains the 30-case Prompt-level regression suite for
`goal-prompt`. The smaller `skills/goal-prompt/evals/` set ships with the
Skill.

The suite checks whether an Agent produces the required goal contract. It does
not prove that the generated goal was executed successfully.

## Run the evaluation

Validate the full suite before a run:

```bash
skill-up validate evals/skill-up/eval.yaml
```

The committed release baseline uses `skill-up 0.9.1`, Codex
`gpt-5.6-luna` with high reasoning, and `gpt-5.6-sol` semantic judges.
Deterministic `expect` and `script` checks remain the default. Use SOL as an
execution model only for a separately reported cohort.

Run from the repository root. The command below prepares a frozen Skill copy
and stores output under `.eval-work/`:

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

Use `--dry-run` to inspect case selection without invoking an Agent. Keep
`--output-dir` absolute. In `skill-up 0.9.1`, a relative output path can make
Agent Judge materials such as `final_message.txt` appear outside the allowed
Judge context.

The YAML pins both the Codex engine and its release-baseline model. A Claude
Code run must override both values:

```bash
skill-up run evals/skill-up/eval.yaml \
  --engine claude_code \
  --model anthropic/<model>
```

## Isolation requirements

A normal run is useful during development. A publishable with-Skill versus
without-Skill comparison must also satisfy these conditions:

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
SOL semantic judges, `parallelism: 1`, and the isolation requirements above.

| Cohort | PASS | FAIL | ERROR |
| --- | ---: | ---: | ---: |
| Luna with Skill | 24 | 6 | 0 |
| Luna without Skill | 9 | 20 | 1 |
| SOL with Skill | 28 | 2 | 0 |

The Luna pair contains 16 Skill-only passes, one baseline-only pass, eight
shared passes, and five shared non-passes. The baseline
`frontend-ui-acceptance` case timed out twice and remains an ERROR.

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

The SOL result measures with-Skill behavior across execution models. It is not
part of the paired Luna delta. A former SOL without-Skill result was discarded
after 23 of 30 transcripts accessed the host copy of `goal-prompt`.

## Limitations

- This is a Prompt-level evaluation. A generated requirement for code, Chrome,
  CI, migration, or rollback does not prove that the action occurred.
- The paired cohort isolated the target, but it was not a fully hermetic
  operating-system environment. One baseline case listed host metadata without
  reading the target Skill, repository, memories, or prior results.
- Static and semantic judges can still miss valid paraphrases or accept precise
  wording that an execution Agent would not follow.
