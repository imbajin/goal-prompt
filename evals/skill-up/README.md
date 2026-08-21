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

```bash
commit="$(git rev-parse HEAD)"
workdir="$PWD/.eval-work/$commit"
target="$PWD/.eval-work/target"

mkdir -p "$target" "$workdir/home" "$workdir/results"
git archive "$commit:skills/goal-prompt" | tar -x -C "$target"

test -f "$target/SKILL.md"
skill-up validate "$PWD/evals/skill-up/eval.yaml"

HOME="$workdir/home" \
skill-up run "$PWD/evals/skill-up/eval.yaml" \
  --output-dir "$workdir/results"
```

Use `--dry-run` to inspect the selected cases without running them. A real run
uses the configured Agent and judge, so local login or credentials must already
work.

Generating `/goal` proves only the Prompt layer. End-to-end task completion
requires a separate execution evaluation.

## HugeGraph two-stage suite

The independent [HugeGraph A/B suite](hugegraph-ab/README.md) adds that second
execution stage for three representative frontend, backend, and documentation
tasks. Its checked-in benchmark remains disabled; deterministic validation and
fake two-stage smoke do not call a real model or change this fast suite.
