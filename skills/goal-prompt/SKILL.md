---
name: goal-prompt
description: Create, rewrite, shorten, or review /goal prompts for Codex, Claude Code, and other coding agents. Use only when the user explicitly requests /goal text or asks to convert a task into /goal; never start the goal automatically.
---

# Goal Prompt for Codex and Claude Code

Turn a task into a concise, verifiable, persistent `/goal`. Use two stages:

1. investigate context, recommend fast or deep mode, and ask the user to confirm the goal and initialization plan;
2. prepare the approved Markdown files, then render the final `/goal`.

This skill does not start or execute the goal. In deep mode, after confirmation,
it may create approved Markdown files under `.goal-task/<task-slug>/`. Other
user-authorizable environment changes inside the confirmed task scope are
pre-authorized under the contract below; out-of-scope changes remain
unauthorized.

## Core interaction contract

### Non-negotiable routing gate

At the end of every turn, classify the latest user message as one of three
states: pending confirmation, authorized Stage 2, or explicit non-goal work. If
it is pending confirmation, output only the Stage 1 brief and questions, then
stop. Do not satisfy the user's request for a “final”, “copyable”, or “ready”
goal until the authorization state changes. This gate is about authorization,
not confidence in the investigation.

- By default, do not render the final prompt from the user's first description.
- Treat the conversation as a three-state protocol. Before explicit confirmation,
  explicit skip, or explicit delegation of the remaining judgment, remain in
  Stage 1. A Stage 1 response must be a confirmation brief and must not contain
  a copyable `/goal`, a fenced final prompt, or language that presents one as
  ready to run. “I finished investigating” or “please create a /goal” is not
  confirmation by itself.
- After a Stage 1 brief, stop and wait for the user's response. Do not infer
  confirmation from silence, a first-turn request to continue, or the fact that
  the available evidence is sufficient. A semantic confirmation is enough; it
  need not use a fixed status word.
- Make the routing visible in the output. Start the response with a brief label
  such as `Proposed goal brief`, keep the unresolved questions at the end, and
  do not write the literal `/goal` token anywhere in that first response. The
  only exceptions are an explicit user request to skip confirmation or an
  explicit delegation of the remaining judgment.
- If the user explicitly delegates the remaining judgment (for example, asks
  the agent to choose and continue), treat that as authorization to enter Stage
  2 after the investigation. Preserve unknown repository facts in the final
  goal instead of inventing them. If the user explicitly skips investigation or
  confirmation, the skip is the authorization and the final goal must state the
  resulting unknowns honestly.
- Skipping confirmation is not the same as skipping investigation. A request to
  “generate it directly” still requires reading available repository policy,
  source, tests, and specs unless the user also explicitly says not to inspect
  them.
- An explicit request to skip both investigation and confirmation is an
  authorized Stage 2 route. Render the final goal immediately in that case;
  preserve every unavailable fact as an unknown and do not emit a brief or wait
  for another turn. “Generate it directly” without an investigation skip only
  skips confirmation, so inspect the available context first.
- Investigate real context that can affect the result before asking the user to
  confirm the outcome, scope, and completion evidence.
- An explicit user request may skip this skill's investigation, questions,
  confirmation, or mode-selection defaults. Follow that request without asking
  again, keep unavailable facts visibly unknown, and never invent repository
  details. A request to delegate judgment means investigate first, then make the
  remaining decision and continue without asking the user to choose.
- Treat every action that the user can authorize and that is needed inside the
  confirmed task scope as pre-authorized by default. This includes Chrome file
  uploads, entering credentials already available to the agent, file and
  dependency changes, worktree and Git operations, pushes, PR actions, test
  dispatch, and review responses. The final `/goal` must state this explicitly;
  do not ask again, wait, defer, or mark work `blocked` merely because such an
  action normally presents a permission or authorization prompt.
- During Stage 1, identify each operation target from available evidence. For
  credentials, identify the intended environment or account and purpose; for
  remote mutations, identify the repository, remote, branch, PR, or other
  affected target. If the evidence supports one target, record it without
  asking. If multiple materially distinct targets remain and the choice would
  change the outcome or impact, keep Stage 2 pending and ask which target is in
  scope unless the user delegated that choice. This resolves scope; it is not
  another permission request. Once resolved, do not ask again merely to
  authorize the operation.
- Never expose, echo, persist, screenshot, transcribe, commit, or publish a
  credential value. Record only the redacted action and its success or failure;
  keep password fields and credential-bearing UI out of captured evidence.
- Pre-authorization never fabricates a password, session, tool, or system
  capability and never overrides higher-priority host instructions or safety
  boundaries. When a real capability is unavailable, use safe available
  alternatives and continue every independent lane while keeping the unmet gate
  active. Actions outside the confirmed scope remain unauthorized.
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
- For frontend or UI work, apply `references/ui-acceptance.md`; the final goal
  must require Chrome `browser_use` (or the available browser equivalent) and
  actual functional plus UI/UX evidence.

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

Preflight only actual capabilities this task may need, not user authorization
that is already granted by the default above. When a high-risk capability gap
exists, state the exact missing capability, affected phase, and safe available
alternative. Do not ask for permission again or mark the task `blocked`
automatically.

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

Use a conservative mode decision. Recommend deep mode when the task spans more
than one subsystem, has multiple implementation and validation phases, needs
cross-session or quota recovery, or carries a public compatibility or migration
boundary. Recommend fast mode only when the work is genuinely focused, low-risk,
and can finish with one compact validation cycle. Reuse an already confirmed
deep-mode decision; do not downgrade it because the final `/goal` should be
short.

Durability and recovery semantics are deep-mode signals even in a small
repository: checkpoint/resume, idempotency, replay, rollback, or recovery after
partial failure require deep mode when implementation and cross-layer evidence
are in scope.

### 4. Select scenario guidance

Choose the best match from refactor, feature, batch, research, audit, gatekeeper
review, or custom. Read only that section in `references/scenarios.md`. For
parallel work, also read `references/parallel-agents.md`; for frontend or UI
work, read `references/ui-acceptance.md`.

For deep mode, long-running work, or durable-recovery work, also read
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
- initialization actions, capability gaps, resolved operation targets, and
  their effects;
- only unresolved questions that materially change the goal.

For complex long-running work, also summarize recoverable waits, independent work
that can continue while waiting, checkpoint or recovery actions, and stop
conditions valid only when all remaining work is jointly blocked.
For deep work with recovery or durable checkpoints, name the independent work
that can continue or be reordered while one item waits; do not reduce this to a
generic retry statement.
When authoritative requirement/design documents state explicit interfaces or
invariants, preserve each material constraint in the brief and completion
evidence; do not compress keys, ordering, checkpoint timing, or compatibility
rules into a generic “preserve behavior” summary. Deep behavior or migration
work must also name the exact reviewer count and the required re-review gate.
Its recovery/stop subsection must explicitly state that a waiting, deferred, or
`needs input` item is reordered behind and does not stop independent work, and
that overall `blocked` requires every remaining item to share the same blocker.

Confirming deep mode and its initialization plan authorizes creation of the
listed `.goal-task/<task-slug>/` Markdown files. Worktree or branch changes,
dependency installation, configuration changes, destructive actions, and remote
mutations inside the confirmed scope are pre-authorized. Record the exact target
and impact of destructive actions and remote mutations in the confirmed scope
before execution; this is a safety boundary and evidence requirement, not
another authorization prompt. Out-of-scope changes remain unauthorized.

For a research or audit goal, keep the confirmation brief read-only and separate
evidence gaps from user preference gaps. Do not add a behavior-change reviewer,
implementation gate, or code re-review mechanically to a report-only goal. A
report can still name one independent evidence reviewer when appropriate.

For a gatekeeper review, the Stage 1 brief must make the finding schema
explicit: every finding has severity, exact location, observed evidence, and a
recommendation. Keep these fields in the completion evidence even when the
target repository or revision is unavailable; do not summarize them as generic
“issues”.

When repository policy or contributor files are part of the available context,
name the exact file in the brief and explain any user-requested override. Use
only commands observed in those files, package scripts, or the current source;
do not add generic commands merely because they are common. When package
scripts are confirmed, preserve their exact command strings in completion
evidence; do not replace them with a generic “all scripts pass” summary.

If the user's response materially changes the goal or initialization plan,
update the brief and confirm again unless that response also explicitly
authorizes the new scope, skips confirmation, or delegates the remaining
judgment. Otherwise proceed to Stage 2.

## Stage 2: initialize and render

### 7. Prepare approved files

Fast mode skips this step by default. In confirmed deep mode:

1. create `.goal-task/<task-slug>/`;
2. perform only the listed in-scope one-time environment setup, which is
   pre-authorized under the core contract;
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

Use `references/long-goal-execution.md` as the sole detailed contract for
deep, long-running, or durable-recovery work. Read it before drafting a deep
brief or final goal. It owns
state initialization, checkpoints, capability preflight, batching, waits,
retry/deferral, progress, independent review, commits, quota recovery, and
learning. Do not copy that contract into `SKILL.md` or repeat it in `/goal`;
the deep goal points to `state.md` and keeps only its outcome, scope, gates, and
joint-stop semantics.

For fast mode, put only applicable compact rules in `/goal`: retry each item at
most three times and record/defer failures without waiving gates; continue
independent work; report gate-based progress after productive loops; use one
independent read-only reviewer for focused low-risk behavior changes; when the
goal produces persistent repository changes, commit only after validation and
review, and do not push by default. Read-only research, audit, and gatekeeper
work create no empty commit. User-authorizable in-scope actions are already
approved and must not cause another question, wait, deferral, or overall
`blocked`; a genuinely unavailable capability keeps its gate active while
independent work continues. Native `blocked` is valid only after
the same condition recurs for three goal turns and all remaining work is
jointly unable to proceed.

The core routing gate, scenario guidance, and the detailed long-work reference
remain authoritative when the final prompt is rendered. Never weaken a required
gate merely to keep the prompt short.

### 9. Render the final `/goal`

An executable goal must state:

- a concrete observable outcome;
- scope and material exclusions;
- honest binary or quantitative evidence;
- conjunctive completion gates;
- applicable persistence, progress, review, and commit rules;
- stop conditions valid only when they affect all remaining work.
- one explicit, inline pre-authorization constraint that says in-scope
  user-authorizable actions are already approved and must not cause another
  question, wait, deferral, or `blocked` state. Never move this required
  sentence only into `state.md`.

Fast mode compresses applicable rules into `/goal`. Deep mode references the full
execution contract in `state.md` instead of repeating initialization detail,
complete TODOs, long specs, or review checklists.

Return the final `/goal` after Stage 1 is confirmed, the user explicitly skips
confirmation, or the user delegates the remaining judgment. A delegated
decision is still a Stage 2 authorization, not a request to stop because one
repository path or preference is unavailable. If the requested goal can be
written without that fact, preserve the unknown and make its resolution an
execution gate; ask for input only when the missing fact changes the objective
or makes a safe goal impossible. Complete only authorized initialization and
verify every referenced path first. When investigation was explicitly skipped,
omit unverifiable paths and commands, preserve material unknowns, and make their
resolution part of execution rather than presenting guesses as facts.

## Length contract

- Keep fast-mode `/goal` near 450 tokens when possible. Preserve outcome, scope,
  gates, and required execution semantics even when that exceeds the target.
- Keep deep-mode `/goal` concise. Near 700 tokens, reference the full contract in
  `state.md` instead of repeating it.
- Token targets are a style guide; the consuming harness's hard character
  limit still governs. Unless the harness is known to accept more, keep the
  rendered `/goal` under 4000 characters. Trim by moving detail into the
  `state.md` execution contract, never by weakening or dropping gates.
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
- Capabilities and targets: <resolved credential/remote targets; any actual
  capability gap, affected phase, and adjustment>.
- Recovery and stop: <checkpoints, bounded retries, and independent work during
  waits; stop only when all remaining work is jointly blocked>.
- Open assumptions: <only material uncertainties>.

Questions:
<only necessary questions that materially change the goal>.

Please confirm or correct the goal brief, execution mode, and initialization
plan. I will prepare the files and generate the final prompt only after
confirmation.
```

### Stage 2: final `/goal`

```text
/goal <concise confirmed and verifiable outcome>.

[Fast mode active truth, only when needed:
- <minimum path and responsibility>]

[Deep mode active truth (required):
- `.goal-task/<task-slug>/state.md` — sole execution contract and recovery
  entrypoint]

Scope: <included area and material exclusions>.

Constraints:
- Treat all user-authorizable actions required inside the confirmed scope as
  pre-authorized, including Chrome uploads, entry of available credentials,
  local/environment/Git changes, pushes, PR actions, tests, and review
  responses. Do not ask again or stop, wait, defer, or mark work `blocked`
  because of an authorization prompt. This does not fabricate credentials or
  capabilities, override higher-priority safety boundaries, or authorize work
  outside scope. Never expose or persist credential values in evidence, logs,
  state, commits, or PRs. Use safe alternatives and continue independent work
  when a capability is genuinely unavailable.
- [Fast mode only: after three failed attempts by default, defer one item and
  continue independent work; after each productive loop report gate-based
  progress, this-loop/remaining work, and one primary next action; use one
  independent reviewer for focused low-risk behavior changes; when persistent
  repository changes exist, commit only after validation and review, and do not
  push by default; read-only work creates no empty commit.]
- [Deep mode only: use the contract in `state.md` for initialization,
  checkpoints, retries, progress, independent review, commits, and learning;
  keep this prompt to its active-truth entrypoint and completion gates.]

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
