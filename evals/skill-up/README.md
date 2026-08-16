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
