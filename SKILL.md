---
name: goal-prompt
description: Create, write, refine, or review /goal prompts for Codex, Claude Code, and coding agents. Use only when users explicitly request /goal text or ask to turn a task into /goal; never run the goal.
---

# Goal Prompt for Codex and Claude Code

Build a short `/goal` control entrypoint through two distinct stages:

1. research and confirm a disposable goal brief;
2. only after confirmation, render the final `/goal` prompt.

The skill produces prompt text only. Do not call goal tools, start the goal, or
create source-of-truth files.

## Non-negotiable interaction contract

- Do not jump from the user's first description directly to a final prompt.
- Investigate available context before asking the user to confirm the goal. Fast
  completion is acceptable only when the task is genuinely simple and already
  grounded; speed is never evidence that the investigation was sufficient.
- Get explicit confirmation of the core outcome, scope, and proof of completion.
  A user-provided existing prompt may count as a draft, but not as confirmation of
  assumptions introduced by the assistant.
- Ask only questions whose answers can materially change the goal. Combine
  tightly related questions and normally ask one to three at a time.
- Keep initialization work out of the final prompt except for one compact
  one-time baseline rule when durable state is actually needed.

## Stage 1: research and confirm

### 1. Confirm the requested artifact

Continue only when the user wants `/goal` prompt text generated, rewritten,
shortened, or reviewed. Do not turn an ordinary task into goal-backed work.

### 2. Investigate the real context

Read all user-provided paths, URLs, specs, constraints, and prior decisions that
can affect the result. When local repository access exists, inspect the nearest
`AGENTS.md`, contributor guidance, current worktree state, relevant source and
tests, package/build scripts, CI configuration, and existing task/spec/design
documents. For remote or time-sensitive claims, use the appropriate live source.

Research must answer, with evidence where available:

- what outcome the user is actually trying to make true;
- current state versus desired state;
- included scope and material exclusions;
- validators or observable evidence that can prove completion;
- unresolved decisions, risks, and dependencies;
- whether durable state is needed and which existing files are still current.

Do not invent commands, paths, dependencies, metrics, or constraints. Do not read
every file mechanically; stop investigating when further inspection is unlikely
to change the brief or the material questions.

### 3. Select and read scenario guidance

Choose one of refactor, feature, batch, research, audit, gatekeeper review, or
custom. Read only the matching section in `references/scenarios.md`.

### 4. Present a disposable goal brief

Return `needs confirmation`, not a `/goal` prompt. Summarize:

- proposed outcome;
- scope and exclusions;
- completion evidence;
- likely source-of-truth set, if any;
- unresolved material assumptions.

Ask the smallest set of material questions needed, and explicitly ask the user to
confirm or correct the brief. This brief is initialization context, not durable
truth. Do not create it as a file or require the eventual executor to reread it.

If the user's answer changes the outcome materially, update the brief and confirm
again. Otherwise proceed to Stage 2.

## Stage 2: render the final prompt

### 5. Classify execution needs

Treat work as complex when it spans phases or subsystems, has many independent
deliverables, needs repeated implementation/verification/review cycles, or must
resume across sessions. Treat it as long-running when it includes slow builds,
remote CI, external waits, environment startup, or quota/session continuity.

Complexity does not imply more truth files. It only changes which execution and
continuity constraints are useful.

### 6. Choose the minimum source of truth

Prefer existing current specs, designs, issue descriptions, and task files. Every
selected file must have a distinct ongoing purpose and expected reader. Merge
overlapping state instead of creating files by category.

Use no sidecar for an ordinary self-contained goal. When durable state is needed,
default to one `.goal-task/<task-slug>/state.md` containing the live plan, TODOs,
evidence, blockers, and next action. Add another file only when it has a genuinely
different lifecycle or authority, for example:

- an existing product spec or design that must remain authoritative;
- a large evidence report that would make live state hard to use;
- a user-required decision log;
- a learning record explicitly requested or justified for a long-running goal.

Do not create `goal.md`; the objective already lives in `/goal`.

If durable files are missing or stale, keep initialization to one compact rule:
perform a fresh audit, create or refresh the minimal live truth, mark the baseline
date/revision, then continue execution from it. Draft inventories and obsolete
baselines are disposable: replace or archive them and remove them from the active
truth list so later iterations do not reread stale artifacts.

For a complex long-running goal, read `references/long-goal-execution.md` and use
only the applicable contract. Read `references/long-goal-learning.md` only when a
learning record is selected.

### 7. Apply the goal quality bar

A ready goal must state:

- the concrete outcome;
- evidence and an honest binary or quantitative success threshold;
- material scope boundaries;
- conjunctive completion gates;
- a concise progress summary at every milestone boundary;
- exceptional conditions that can stop all remaining work.

Rewrite vague activity goals into observable outcomes. Do not add decorative
metrics. Every applicable completion gate must pass; a conditional gate may be
excluded only when demonstrably inapplicable or explicitly waived by the user.

### 8. Bias execution toward completion

The prompt must tell the executor to keep the goal active until all scoped
completion gates are satisfied. One item that cannot proceed is a scheduling
signal, not permission to mark the whole goal `blocked`: record the evidence,
mark the item waiting or deferred, move it and its dependents behind independent
work, and continue the highest-value scoped task. Diagnose, fix, or finitely
retry actionable failures.

CI queues or failures, API adjustments, transient outages, test failures, and
quota waits are not reasons to end while meaningful scoped work remains. Avoid
self-imposed shortcuts, partial-success exits, arbitrary time limits, and new stop
conditions not grounded in the confirmed brief.

Do not set the overall goal to `blocked` because of a recoverable failure, a
missing optional dependency, a non-material ambiguity, or a decision that can be
handled with a safe reversible assumption. Before using `blocked`, perform
bounded recovery, try authorized alternatives, split work or narrow the next
action without changing the confirmed scope, reorder work, finish all independent
scoped work, and ask the user only for a decision that materially changes the
goal. Never remove confirmed scope or a completion gate without renewed user
confirmation.

Set the overall goal to `blocked` only as an exceptional terminal state when
every meaningful remaining scoped task depends on the same requirement conflict,
safety boundary, unauthorized scope expansion, unavailable mandatory independent
review, or verified external dependency. State completed work, evidence,
deferred items, and the exact decision or external change required.

### 9. Report milestone progress

After every milestone or meaningful phase boundary, require a compact user-facing
summary even when durable state is also updated:

```text
Progress [██████░░░░] 60%
Done: <completed milestone and key evidence>; Remaining: <main open item>.
Next: <one primary action>.
```

Base the percentage on completed scoped milestones, deliverables, and completion
gates rather than elapsed time or effort spent. Use an exact percentage when the
denominator is fixed; otherwise use a coarse evidence-based estimate and label it
`estimate`. Reserve `100%` for the point when every applicable completion gate
passes. Keep the summary to three short lines.

### 10. Require independent review for behavior changes

For production code, public APIs, tests/test infrastructure, build/CI logic,
dependencies, migrations, deployment, or behavior-changing configuration, keep
this rule in the prompt:

```text
After implementation and verification, an independent read-only reviewer
subagent must review the final diff against the goal and test evidence. The
implementation worker must not act as reviewer. After fixes, the independent
reviewer must re-review affected changes. If no independent reviewer can be
created, finish all work that does not depend on review, then stop and ask the
user; do not claim completion.
```

Completion also requires all actionable findings fixed or explicitly accepted,
no unresolved high-severity finding, and the final summary naming the reviewer
and review/re-review result. Do not force this gate for pure documentation or
read-only work unless repository policy or the user requires it.

### 11. Render and check

Return `ready` only after Stage 1 confirmation and when the final prompt passes
the quality and length gates. Otherwise return `needs confirmation` with the
updated brief and material question. Never use a pseudo-precise audit score.

## Length contract

- Ordinary prompt: target 12-25 lines and no more than about 450 tokens.
- Complex prompt: hard limit about 700 tokens.
- Move details into already-selected truth files; do not create extra files only
  to satisfy the prompt length.

The final prompt should contain only:

- one or two sentences for the confirmed outcome;
- only the minimal active source-of-truth paths, when needed;
- concise scope and exclusions;
- core execution constraints, including continue/reprioritize semantics;
- one compact milestone progress-reporting rule;
- three to six conjunctive completion gates;
- one to three exceptional all-work-blocked stop conditions;
- the independent reviewer gate when behavior changes;
- an optional token-budget line when justified or requested.

Do not include the research transcript, disposable brief, step-by-step
implementation, full TODO list, long spec recap, detailed review checklist,
repeated document content, or unverified assumptions.

## Output templates

### Stage 1: needs confirmation

```text
Proposed goal brief
- Outcome: <observable after-state>.
- Scope: <included area>; excludes <material exclusions>.
- Completion evidence: <validators or observable proof>.
- Minimal truth: <none, existing paths, or one proposed live-state path>.
- Open assumptions: <only material uncertainties>.

Questions:
1. <one to three material questions>.

Please confirm or correct this brief. I will generate the final `/goal` only
after confirmation.

needs confirmation
```

### Stage 2: ready

```text
/goal <one or two sentences describing the confirmed, verifiable outcome>.

[Source of truth, only when needed:
- <minimal active path(s)>]

Scope: <included area and material exclusions>.

Constraints:
- Keep the goal active until every applicable completion gate passes. Record an
  item that cannot proceed as waiting/deferred, move it and its dependents behind
  independent work, and never mark the overall goal blocked while meaningful
  scoped work remains.
- After each milestone, report a three-line progress bar summary with percentage,
  completed/remaining items, and one next primary action. Base the percentage on
  scoped milestones and gates; label it as an estimate when no fixed denominator
  exists.
- [If initialization is needed: perform one fresh baseline audit, update the
  minimal live truth, retire stale drafts from the active truth list, then
  continue.]
- [For code changes: independent read-only reviewer; no worker self-review.]

Complete only when all applicable conditions are true:
1. <observable outcome or artifact>.
2. <required validators and recorded evidence>.
3. <remaining confirmed gates>.
4. [For code changes: review and any required re-review are complete with no
   unresolved blocker.]

Set the overall goal to blocked only if every meaningful remaining scoped task
depends, after bounded recovery, authorized alternatives, reprioritization, and
completion of independent work, on:
- <confirmed exceptional conflict, boundary, or mandatory dependency>.
- [For code changes: independent review remains unavailable after all
  review-independent work is complete.]

[Optional only when requested: Use a token budget of <N> tokens.]
```

## Final response

During Stage 1, return only the disposable brief, material questions, and
`needs confirmation`; do not include a `/goal` code block.

During Stage 2, return:

1. one Markdown code block containing the copy-pasteable `/goal` prompt;
2. no more than eight short lines explaining grounded choices and active truth;
3. one line containing `ready`.

Do not start the goal or create referenced files.

When maintaining this skill, read `references/fusion-notes.md` for source lineage
and the rationale behind retained, modified, omitted, and locally added rules.
