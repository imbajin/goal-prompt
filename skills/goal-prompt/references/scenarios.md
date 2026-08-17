# Scenario Guidance

Read only the section matching the user's task. These rules extend the two-stage
flow in `SKILL.md`; they are not complete prompt templates. Use them during
research to improve the confirmation brief. By default, do not render `/goal`
before the user confirms; follow the core contract when the user explicitly
skips confirmation or delegates the remaining judgment.

## Refactor

- State the intended after-state and the API or external behavior that must stay
  stable.
- Inspect callers, tests, and public contracts before confirmation; do not infer
  the boundary from a directory name.
- Bound scope to the affected subsystem and name adjacent exclusions.
- Use repository-provided targeted tests plus the smallest relevant broader gate.
- Apply the review count selected by task scale and risk: 1 reviewer for a
  focused low-risk fast-mode change, or 3 for deep-mode or major changes.
- Defer unapproved API, schema, or dependency changes. Ask only after completing
  other in-scope work and only when the decision blocks all remaining work.

## Feature

- Prefer existing specs, designs, and task files.
- Compare desired behavior, current implementation, and existing tests before
  drafting the brief.
- In deep mode create `state.md`; split out `todo.md` or `design.md` only for
  large TODO volume or durable design decisions.
- Map top-level gates to observable behavior and repository validators.
- Use 3 independent reviewers at major behavior-change milestones and re-review
  after fixes.

## Batch

- State the source of the set and its exact size when known.
- Verify whether membership can change.
- Keep per-item detail in `todo.md`, `state.md`, or a formal evidence artifact,
  not in `/goal`.
- Create a separate `todo.md` only for a large or frequently changing list.
- Use exact percentages for a fixed denominator. When membership can change, use
  a coarse evidence-based value labeled `estimate`.
- Define what happens when an item disappears, changes, or cannot be reproduced.
- Form batches by shared module, root cause, or validation surface, not an
  arbitrary item count.

## Research

- Name the decision the research must support and its evidence standard.
- Inspect accessible primary sources before confirmation; distinguish missing
  evidence from a missing user preference.
- Restrict writes to named report files when appropriate.
- Cite real files, lines, command output, or primary sources.
- Keep a pure read-only research goal free of implementation-only gates. Use 1
  independent reviewer by default for the report and evidence, not a code
  reviewer or behavior-change re-review unless the user asks for remediation.
- Exhaust accessible evidence and independent research lanes before requesting
  input because mandatory evidence is inaccessible or authorities conflict.

## Audit

- Name the authoritative comparison source and audit units.
- Inspect both the claimed baseline and a representative implementation slice
  before confirming scope.
- Separate observed evidence from inference and mark runtime-only questions.
- Include a compact findings summary, evidence, and actionable priorities.
- Put detailed audit rows in the formal report, not `/goal`.
- Stay read-only unless the user explicitly expands scope to remediation; use
  1 independent reviewer by default.

## Gatekeeper review

This means the goal itself decides whether a branch, PR, or change is ready. It
is distinct from independent review after implementation.

- Stay read-only: do not implement, push, merge, or rebase.
- Review the actual final diff and relevant validation evidence.
- In Stage 1 verify the target revision, available checks, and comments.
- Report severity, exact location, evidence, and recommendation.
- In the Stage 1 brief, make these four finding fields explicit as completion
  evidence even when the repository or revision is unavailable; do not collapse
  them into a generic “issues” line.
- Use a small verdict set such as `ready`, `needs work`, or `blocked`.
- Refresh when the revision changes. If one validation is unavailable, continue
  other review work first.

## Custom

- Select only when no other scenario applies.
- Focus clarification on outcome, evidence, and stop conditions that genuinely
  affect all remaining work.
- Add only constraints supported by the user or repository evidence.
- Choose files, progress, and reviewer rules based on task complexity and
  behavioral risk; do not stack them mechanically.
