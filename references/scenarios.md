# Scenario Guidance

Read only the section matching the user's task. These are deltas from the core
two-stage workflow in `SKILL.md`, not complete prompt templates. Use the points
below during research to improve the disposable brief; do not render a final
prompt before the user confirms it.

## Refactor

Use when changing one subsystem while preserving externally visible behavior.

- Name the intended after-state and the API or behavior that must stay stable.
- Inspect current callers, tests, and public contracts before asking for
  confirmation; do not assume the refactor boundary from a directory name alone.
- Bound scope to the affected subsystem and identify adjacent exclusions.
- Use repository-provided targeted tests plus the smallest relevant broader gate.
- Require the independent reviewer gate because implementation changes code.
- Defer work requiring an unapproved API, schema, or dependency change; ask only
  after completing independent in-scope work and only if the decision blocks all
  meaningful remaining work.
- For a long refactor, freeze related low-risk edits by shared validation surface,
  then run the smallest broader gate at phase boundaries rather than after every
  edit.

## Feature

Use for new user-visible or system behavior, with or without an existing spec.

- Prefer an existing spec, design, and task file as source of truth.
- Compare the requested behavior with current implementation and tests before
  drafting the goal brief.
- If durable state is needed and no current plan exists, prefer one live-state
  file; split it only when content has a different authority or lifecycle.
- Map top-level completion gates to observable behavior and repository validators.
- Require independent review and re-review for implementation changes.
- Defer conflicting requirements or an unapproved public-surface expansion until
  independent in-scope work is complete; ask only if it then blocks all remaining
  meaningful work.

## Batch

Use when processing a known or externally enumerable set of similar items.

- State the source of the set and the exact item count when known.
- Verify the set and whether membership can change before confirmation.
- Keep per-item detail in the selected live-state or evidence file, not in
  `/goal`.
- Add a separate progress file only when a long batch cannot be resumed safely
  from the live-state file; report at item-count checkpoints.
- Use an exact percentage when the item count is fixed. If membership can change,
  report a coarse estimate based on verified items and label it `estimate`.
- Define what happens when an item disappears, changes, or cannot be reproduced.
- Review the final aggregate diff independently when code behavior changes.
- Form implementation batches by shared module, root cause, or validation surface;
  do not use an arbitrary fixed item count.

## Research

Use for read-only investigation, architecture discovery, or decision support.

- Name the decision the research must enable and the evidence standard.
- Inspect accessible primary sources before asking the user to confirm the
  question; distinguish missing evidence from a missing user preference.
- Restrict writable output to named report files when appropriate.
- Require real citations to files, lines, commands, or primary sources.
- Do not add the code-review gate unless behavior-changing files will be edited.
- Exhaust accessible evidence and independent research lanes before stopping on
  inaccessible required evidence or irreconcilable authoritative sources.

## Audit

Use to compare implementation against a documented claim, spec, or expected flow.

- Name the authoritative comparison source and the units being audited.
- Inspect both the claimed baseline and a representative implementation slice
  before confirming the audit boundary.
- Separate observed evidence from inference and mark runtime-only questions.
- Require a compact findings summary and actionable priorities in the report.
- Keep detailed audit rows in the report file, not in `/goal`.
- Remain read-only unless the user explicitly expands the goal to remediation.

## Gatekeeper review

Use when the goal itself is to decide whether branches, pull requests, or changes
are ready. This is different from the independent reviewer gate applied after a
code implementation goal.

- Keep the reviewer read-only: no implementation, push, merge, or rebase.
- Review the actual final diff and relevant validation evidence.
- During Stage 1, verify the target revision and available checks/comments before
  confirming the review question.
- Produce findings with severity, precise location, evidence, and recommendation.
- Use a small explicit verdict set such as `ready`, `needs work`, or `blocked`.
- Refresh a changed revision and defer unavailable validation while other review
  work remains; stop only when no valid verdict can be produced after bounded
  recovery and reprioritization.

## Custom

Use only when none of the other scenarios fits.

- Start from the ordinary or complex template in `SKILL.md`.
- Spend clarification effort on the outcome, evidence, and stop conditions.
- Add only constraints supported by the user's request or repository evidence.
- Apply sidecar, progress, and independent-review rules based on task complexity
  and behavior impact rather than adding them mechanically.
