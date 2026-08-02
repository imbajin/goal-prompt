---
name: goal-prompt
description: Create, rewrite, shorten, or review /goal prompts for Codex, Claude Code, and other coding agents. Use only when the user explicitly requests /goal text or asks to convert a task into /goal; never start the goal automatically.
---

# Goal Prompt for Codex and Claude Code

Turn a task into a concise, verifiable, persistent `/goal`. Use two stages:

1. investigate context, recommend fast or deep mode, and ask the user to confirm the goal and initialization plan;
2. prepare the approved Markdown files, then render the final `/goal`.

This skill does not start or execute the goal. In deep mode, after confirmation,
it may create approved Markdown files under `.goal-task/<task-slug>/`; other
environment changes still require explicit authorization.

## Core interaction contract

- By default, do not render the final prompt from the user's first description.
- Investigate real context that can affect the result before asking the user to
  confirm the outcome, scope, and completion evidence.
- An explicit user request may skip this skill's investigation, questions,
  confirmation, or mode-selection defaults. Follow that request without asking
  again, keep unavailable facts visibly unknown, and never invent repository
  details. A request to delegate judgment means investigate first, then make the
  remaining decision and continue without asking the user to choose.
- User control over this workflow does not override higher-priority host
  instructions, safety boundaries, or permissions. If they conflict, explain
  the exact constraint and request only the decision needed for a feasible goal.
- Ask only questions whose answers materially change the goal. Do not interrupt
  early for questions that evidence, a safe reversible assumption, or later
  execution can resolve.
- Recommend fast or deep mode, but let the user confirm it. Do not ask again when
  the user already selected a mode.
- Keep one-time preparation in initialization, not in the enduring `/goal`. Put
  unfinished preparation directly in `state.md`; after completion, remove the
  steps and retain only results that still matter.
- Do not create `goal.md`; the objective already lives in `/goal`.
- Do not mark the whole goal `blocked` because of an ordinary failure, missing
  permission, resource limit, or possible question.

## Stage 1: investigate and confirm

### 1. Confirm the requested artifact

Continue only when the user explicitly wants `/goal` prompt text generated,
rewritten, shortened, or reviewed. Do not turn an ordinary task into goal-backed
work or execute the goal inside this skill.

When rewriting, shortening, or reviewing a draft, separately check whether it
defines an observable after-state and whether its evidence covers the full scope.
Activity-only language such as "improve", "polish", "optimize", or "refactor" is
not verifiable. Test success alone does not prove completion when the task also
includes behavior, compatibility, migration, documentation, deployment, or
review requirements.

### 2. Investigate the real context

Read all user-provided paths, URLs, specs, constraints, and prior decisions that
can affect the goal. When a local repository is available, inspect the nearest
`AGENTS.md`, contributor guidance, current worktree, relevant source and tests,
build scripts, CI, and existing issues, TODOs, specs, or design documents. Verify
remote and time-sensitive information from live sources.

Use evidence where possible to determine:

- the result the user actually wants;
- the gap between current and desired state;
- scope, material exclusions, and invariants;
- validators or observable evidence that prove completion;
- unresolved decisions, risks, and external dependencies;
- whether the task must resume across phases, sessions, or quotas;
- whether existing truth files remain current;
- whether the current agent's write, command, network, subagent, Git, and
  connector permissions could obstruct later execution.

Preflight only capabilities this task may need. When a high-risk gap exists,
state the exact missing capability, affected phase, and suggested adjustment.
Do not expand permissions or mark the task `blocked` automatically.

Do not invent commands, paths, dependencies, metrics, or constraints, and do not
read every file mechanically. Stop when more investigation is unlikely to change
the brief, mode recommendation, or material questions.

### 3. Recommend an execution mode

#### a. Fast / small-task mode

Use for focused, lower-risk, well-grounded work that normally fits one continuous
execution cycle.

- Perform targeted, time-bounded research without unrelated fine-grained
  inventory.
- Create no sidecar by default.
- Create `state.md` only when recovery continuity is genuinely needed.
- Do not pre-create `todo.md`, `design.md`, or `lessons.md`; add one only after a
  concrete failure, reusable lesson, or user request triggers it.
- Put the applicable compact execution rules directly in `/goal`.

#### b. Deep / long-task mode

Use for work spanning phases or subsystems, with many deliverables, repeated
implementation and validation, remote waits, or cross-session recovery.

- Complete one sufficient baseline investigation of the current revision,
  existing documents, execution environment, and material risks.
- After the user confirms initialization, create a non-empty `state.md` and
  create `todo.md`, `design.md`, or other approved files only when needed.
- Put the full execution contract in `state.md`; keep only the outcome, scope,
  gates, truth entrypoint, and essential stop semantics in the final `/goal`.
- Summarize learning briefly after each productive loop, but create or update
  `lessons.md` only when evidence-backed reusable content exists.

Complexity does not imply more files. Do not treat deep mode as a mandatory
four-file bundle.

### 4. Select scenario guidance

Choose the best match from refactor, feature, batch, research, audit, gatekeeper
review, or custom. Read only that section in `references/scenarios.md`.

For complex long-running work, also read
`references/long-goal-execution.md`. Read
`references/long-goal-learning.md` only when a learning record is selected.

### 5. Design the minimum initialization set

Prefer current specs, designs, issues, and task files. A new file must have a
distinct purpose, reader, and lifecycle; never create an empty placeholder.

Only these four files are candidates under `.goal-task/<task-slug>/`:

| File | Responsibility | Creation condition |
| --- | --- | --- |
| `state.md` | Live status, phase, active-truth index, gate evidence, work summary, unfinished initialization, and next action | Always in deep mode; in fast mode only for cross-turn recovery |
| `todo.md` | Large or frequently changing executable work items | TODO detail would crowd `state.md` or needs independent batch maintenance |
| `design.md` | Confirmed, durable design decisions, interfaces, and invariants | Material design decisions exist and no more authoritative design already exists |
| `lessons.md` | Evidence-backed reusable lessons and promotion candidates | In deep mode only when real lessons exist; in fast mode only after a user request or concrete failure |

Do not create overlapping `progress.md`, `blockers.md`, `decisions.md`, or
`goal.md`. A large evidence report or formal spec may use the task's required
artifact path, but it is not a default initialization file.

Keep responsibilities separate:

- `state.md` holds current execution truth and links elsewhere. Do not duplicate
  `/goal` gates, full design, long TODOs, or lesson text. With `todo.md`, keep
  only item counts, dependency summary, and the link. Unfinished one-time work
  may appear under "Initialization TODO"; remove its steps after completion and
  retain only environment results or constraints that still matter.
- `todo.md` answers "what remains?" When present, item-level state and
  waiting/deferred markers live only here.
- `design.md` answers "what was decided and why?" It does not track daily work.
- `lessons.md` holds validated, reusable lessons, not chronology.

First follow the host agent's instruction priority. Within task materials, use:

```text
latest user confirmation > authoritative spec/design > issue/todo > state
```

`state.md` is an active index and execution record; it cannot override
authoritative product or design truth. Refresh initialization incrementally only
when scope, repository baseline, key design, or environment materially changes.

### 6. Present the confirmation brief

Unless the user explicitly skips confirmation or delegates the remaining
judgment, Stage 1 returns a confirmation brief, not `/goal`. Include:

- proposed outcome;
- scope and exclusions;
- completion evidence;
- recommended mode and rationale;
- existing files to reuse and new files to create;
- initialization actions, permission risks, and their effects;
- only unresolved questions that materially change the goal.

For complex long-running work, also summarize recoverable waits, independent work
that can continue while waiting, checkpoint or recovery actions, and stop
conditions valid only when all remaining work is jointly blocked.

Confirming deep mode and its initialization plan authorizes creation of the
listed `.goal-task/<task-slug>/` Markdown files. Worktree or branch changes,
dependency installation, configuration changes, destructive actions, and remote
mutations require the exact target and impact to be listed and explicitly
authorized. Do not ask again when the same confirmation already covers them.

If the user's response materially changes the goal or initialization plan,
update the brief and confirm again unless that response also explicitly
authorizes the new scope, skips confirmation, or delegates the remaining
judgment. Otherwise proceed to Stage 2.

## Stage 2: initialize and render

### 7. Prepare approved files

Fast mode skips this step by default. In confirmed deep mode:

1. create `.goal-task/<task-slug>/`;
2. perform only the listed, explicitly authorized one-time environment setup;
   do not begin implementation within the goal's scope;
3. create or refresh `state.md` with the baseline, active-truth index, execution
   contract, and next action;
4. create non-empty `todo.md`, `design.md`, or `lessons.md` only when its trigger
   is satisfied;
5. verify every path that the final `/goal` will reference;
6. replace or archive stale drafts and remove them from active truth.

Initialization files and authorized environment preparation serve later goal
execution; they do not start the goal. Do not repeat completed one-time actions
in `/goal`. Put unfinished actions under `state.md`'s "Initialization TODO" and
simplify or remove them promptly after completion.

### 8. Write the execution contract

#### Persistent execution and retry

- Unless the user specifies otherwise, try one item at most three times. If it
  still fails, record evidence, defer it, and continue all independent work.
- Diagnose and repair recoverable failures, narrow the next action, or use an
  authorized alternative.
- Under resource pressure, first reduce concurrency or batch size, change
  validation cadence, or adjust resource use; defer the item only if needed.
- Deferral is not a waiver. An unmet gate remains active, so progress cannot be
  reported as `100%`.
- Mark ordinary permission or authorization gaps `needs input` and continue
  independent work; do not mark the entire goal `blocked`.

Set the overall goal `blocked` only when the user explicitly defines that rule,
or when bounded recovery, authorized alternatives, task splitting,
reprioritization, and all independent work are exhausted and every meaningful
remaining item still depends on the same logical conflict, safety boundary, or
verified mandatory external dependency.

#### Loop progress

After every productive execution loop, and when a major milestone review or
commit spans its own loop, report:

```text
Progress [██████░░░░] 60% (3/5 gates)
This loop: <completed work and key evidence>; Remaining: <main open work>.
Next: <one primary action>.
```

Calculate percentage from scoped milestones, deliverables, and completion gates,
not elapsed time or effort. Use a coarse evidence-based value labeled `estimate`
when the denominator is unstable. Never report `100%` before all applicable
gates pass. Do not report tool calls, waits, or no-change loops separately.
Combine review and commit when they occur in the same loop.

#### Independent review

- For a focused, low-risk behavior change in fast mode, use 1 independent
  read-only reviewer by default.
- For deep-mode or major behavior changes, use exactly 3 independent read-only
  reviewers at the final major milestone; apply the same rule to intermediate
  major milestones in deep work.
- For a large change, all 3 first scan global risk, then focus respectively on
  correctness/tests, design/boundaries, and security/maintainability.
- Pure documentation, read-only research, or analysis uses 1 independent
  reviewer by default; the user may increase the count.
- A reviewer may be a subagent, isolated session, or equivalent independent
  review tool. The implementation worker cannot substitute for one.
- Run at most 3 fix/re-review rounds by default. If review still fails, record
  and defer affected work, continue independent work, and do not claim the gate.
- If required reviewers are unavailable, raise an early high-risk warning,
  finish review-independent work, and remain `needs input`; do not self-review
  or mark the whole goal `blocked` automatically.

#### Milestone commits

- When a major milestone produces persistent repository changes, create a local
  commit promptly after applicable validation and review pass. Do not create
  empty commits for read-only research, analysis, audits, or gatekeeper reviews.
- Fix high-severity findings, test failures, and unmet gates before committing by
  default.
- If current changes are a required baseline for later work, an intermediate
  checkpoint commit may record the risks and unmet gates. It does not mean review
  passed or complete those gates.
- Do not push by default. Pushes, PRs, releases, and deployments require explicit
  authorization.

#### Learning

At the end of each productive deep-mode loop, briefly summarize disproven
assumptions, effective recovery, and potentially reusable rules. Write to
`lessons.md` only when the content is evidence-backed and reusable.

Learning may propose candidates for repository rules, global rules, or Memory,
but cannot promote them automatically. Changing AGENTS instructions or Memory
requires separate explicit authorization.

### 9. Render the final `/goal`

An executable goal must state:

- a concrete observable outcome;
- scope and material exclusions;
- honest binary or quantitative evidence;
- conjunctive completion gates;
- applicable persistence, progress, review, and commit rules;
- stop conditions valid only when they affect all remaining work.

Fast mode compresses applicable rules into `/goal`. Deep mode references the full
execution contract in `state.md` instead of repeating initialization detail,
complete TODOs, long specs, or review checklists.

Return the final `/goal` after Stage 1 is confirmed, the user explicitly skips
confirmation, or the user delegates the remaining judgment. Complete only
authorized initialization and verify every referenced path first. When
investigation was explicitly skipped, omit unverifiable paths and commands,
preserve material unknowns, and make their resolution part of execution rather
than presenting guesses as facts.

## Length contract

- Keep fast-mode `/goal` near 450 tokens when possible. Preserve outcome, scope,
  gates, and required execution semantics even when that exceeds the target.
- Keep deep-mode `/goal` concise. Near 700 tokens, reference the full contract in
  `state.md` instead of repeating it.
- Do not create files merely to shorten the prompt; every truth file needs a
  distinct responsibility.

The final `/goal` contains only:

- the confirmed outcome;
- minimum active-truth paths;
- concise scope and exclusions;
- core persistence and reprioritization semantics;
- all conjunctive completion gates;
- exceptional stop conditions that genuinely affect all remaining work;
- a token budget only when the user requested it.

## Output templates

### Stage 1: confirmation brief

```text
Proposed goal brief
- Outcome: <observable after-state>.
- Scope: <included area>; excludes <material exclusions>.
- Completion evidence: <validators or observable proof>.
- Recommended mode: <fast/deep>; rationale: <task properties>.
- Active truth: <existing paths to reuse>.
- Proposed initialization: <no files, or each file and its purpose>.
- Permission risks: <none, or exact capability, affected phase, and adjustment>.
- Recovery and stop: <checkpoints, bounded retries, and independent work during
  waits; stop only when all remaining work is jointly blocked>.
- Open assumptions: <only material uncertainties>.

Questions:
<only necessary questions that materially change the goal>.

Please confirm or correct the goal brief, execution mode, and initialization
plan. I will prepare the files and generate the final `/goal` only after
confirmation.
```

### Stage 2: final `/goal`

```text
/goal <concise confirmed and verifiable outcome>.

[Active truth, only when needed:
- <minimum path and responsibility>]

Scope: <included area and material exclusions>.

Constraints:
- Keep the goal active until all applicable gates pass. After three failed
  attempts by default, defer one item and continue independent work. Mark
  permission or authorization gaps `needs input`, not automatically `blocked`.
- After each productive loop, report a three-line summary with gate-based
  percentage, this-loop/remaining work, and one primary next action. Report a
  review or commit that spans its own loop; combine them within one loop.
- [Independent review: 1 reviewer for a focused low-risk fast-mode change;
  exactly 3 for deep-mode or major behavior changes; the implementer cannot
  substitute, and fixes require re-review.]
- [Persistent repository changes: create a local commit after applicable
  validation and review pass; do not push by default.]
- [Deep mode: use the contract in state.md for active truth, review, commits,
  and learning.]

Complete only when all applicable conditions are true:
1. <observable outcome or artifact>.
2. <required validators and evidence>.
3. <remaining confirmed gates>.
4. [Behavior change: required independent review and re-review are complete with
   no unresolved high-severity finding.]

Set the overall goal `blocked` only when every meaningful remaining item, after
recovery, reprioritization, and completion of independent work, still jointly
depends on <confirmed logical conflict, safety boundary, or mandatory external
dependency>.

[Only when requested: Use a budget of <N> tokens.]
```

## Final response

During Stage 1, return only the goal brief, material questions, and a clear
request for confirmation; do not require a fixed status string or include a
`/goal` code block. Skip this response format when the user explicitly skips
confirmation or delegates the remaining judgment.

During Stage 2, return:

1. one Markdown code block containing the copy-pasteable `/goal`;
2. a short explanation limited to mode, initialization files, and grounded
   tradeoffs.

Do not start the goal.
