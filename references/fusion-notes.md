# Design Lineage and Decisions

This project combines ideas from two references without copying either verbatim:

- OpenAI `define-goal`: <https://github.com/openai/skills/blob/main/skills/.curated/define-goal/SKILL.md>
- `win4r/goal-prompt-builder`: <https://github.com/win4r/goal-prompt-builder>

## Retained

From OpenAI `define-goal`:

- concrete outcomes instead of activity descriptions;
- explicit evidence and honest binary or quantitative thresholds;
- bounded scope and conditions that genuinely require stopping to ask;
- questions only when missing information changes the goal;
- the prompt builder does not execute the goal.

From `goal-prompt-builder`:

- a copy-pasteable `/goal`;
- outcome, scope, constraints, conjunctive gates, and exceptional stop conditions;
- repository investigation and scenario-specific rules;
- a brief explanation of grounded decisions after generation.

## Major modifications

- Replace one-stage generation with "investigate and confirm, then initialize and
  render."
- Recommend fast or deep mode automatically, with user confirmation.
- In deep mode, create approved `.goal-task/<slug>/` Markdown files after
  confirmation.
- Keep one-time environment preparation out of the enduring prompt. Put
  unfinished work under `state.md`'s "Initialization TODO", then simplify or
  remove it after completion.
- Derive gate and stop-condition counts from actual requirements.
- End Stage 1 with `needs confirmation`; use the final `/goal` code block itself
  as the Stage 2 completion signal, with no extra status suffix.
- Ground commands, paths, and constraints in repository or user evidence.
- Include a token budget only when the user explicitly requests it.

## Initialization file design

Select files by responsibility, not task complexity:

- fast mode creates no file by default and uses `state.md` only for recovery;
- deep mode always creates a non-empty `state.md`;
- use `todo.md` only for large or frequently changing work items;
- use `design.md` only for confirmed decisions that need durable authority;
- create `lessons.md` only for evidence-backed reusable learning.

Do not create `goal.md` or mechanically add `progress.md`, `blockers.md`, or
`decisions.md`. A large report or formal spec may be a task artifact, but is not
a default initialization file.

`state.md` is live state and an index; it cannot override an authoritative spec
or design. Within task materials use:

```text
latest user confirmation > authoritative spec/design > issue/todo > state
```

## Persistent execution and state

- Try an ordinary failed item at most three times by default, then record and
  defer it while continuing independent work.
- Mark permission or authorization gaps `needs input`, not overall `blocked`.
- Address resource limits first by reducing concurrency or batch size, or
  adjusting resource use.
- A deferred item's completion gate remains active, so progress cannot be
  reported as `100%`.
- Use overall `blocked` only under a user-defined rule or when all remaining work
  shares one logical conflict, safety boundary, or verified mandatory external
  dependency.

## Progress, review, and commits

- Report a three-line summary after each productive loop and when a major review
  or commit spans its own loop; combine them when they occur in one loop.
- Derive percentage from scoped milestones, deliverables, and gates; label it
  `estimate` when the denominator is unstable.
- Use exactly 3 independent reviewers at final behavior-change milestones and at
  intermediate major milestones in deep work.
- Use 1 independent reviewer by default for pure documentation, read-only
  research, or analysis.
- Run at most 3 fix/re-review rounds by default. Record and defer unresolved
  work; do not call it complete.
- After validation and review pass, create a local commit promptly for persistent
  repository changes. Do not create empty commits for read-only work and do not
  push by default.
- A required downstream baseline may be checkpointed with explicit risks, but
  that does not mean review passed.

## Learning

Deep mode briefly summarizes learning after each productive loop, but writes
`lessons.md` only for real, reusable, evidence-backed content. Fast mode enables
it only after a user request or concrete failure.

Learning may become a candidate for repository rules, global rules, or Memory,
but cannot be promoted automatically. Changing AGENTS instructions or Memory
requires separate explicit authorization.

These decisions address premature finalization, repeated initialization,
overlapping sidecars, premature blocking after ordinary failure, idle waits,
unstable progress reporting, insufficient independent review, and loss of
cross-loop learning.
