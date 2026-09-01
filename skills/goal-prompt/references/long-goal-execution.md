# Long-Goal Execution Loop

Use for deep work with remote CI, slow validation, external environments,
multiple phases, cross-quota recovery, or durable recovery semantics such as
checkpoint/resume, idempotency, replay, rollback, or partial-failure recovery.
Put the full contract in
`.goal-task/<task-slug>/state.md`; keep only its entrypoint and completion gates
in `/goal`.

## Initialization and state ownership

Deep mode always creates a non-empty `state.md` containing:

- current baseline revision and environment;
- active-truth index and authority order;
- phases, current gate state, and priority;
- validation and reviewer evidence;
- waiting/deferred summary, recovery state, and dependencies;
- next primary action and resume entrypoint;
- applicable progress, retry, review, commit, and learning rules.

## Compaction-safe checkpoints

Before context compaction, quota wait, or session handoff, update `state.md` with
the current gate percentage, completed and remaining items, latest commit,
validation evidence, active waits or deferrals, and one next action. After every
major milestone commit, the next progress report must include the commit and a
short summary of what is complete now. A later session must be able to resume
from `state.md` without reconstructing progress from conversation history.

Split content only when responsibility is genuinely independent:

- large or frequently changing items go to `todo.md`;
- confirmed durable design decisions go to `design.md`;
- evidence-backed reusable lessons go to `lessons.md`.

When `todo.md` exists, maintain item-level state and waiting/deferred markers
only there. Keep counts, dependency summary, and its link in `state.md`.

Put one-time preparation that cannot be completed in advance under
"Initialization TODO" in `state.md`, including action, authorization state,
completion condition, and current result. After completion, remove the steps and
retain only environment results or constraints that still matter.

At initialization, audit the revision, existing materials, and execution
permissions once. Refresh incrementally only when scope, baseline, key design, or
environment materially changes.

## Authorization, capability, and environment preflight

In the first loop, verify only the write, command, network, subagent, Git,
connector, and wakeup capabilities this task may use. Immediately flag a gap
that could affect a later phase:

- the exact missing capability;
- affected work or gate;
- the adjustment the user can make.

All user-authorizable operations required inside the confirmed task scope are
pre-authorized by default, including Chrome uploads, entering credentials
already available to the agent, local and environment changes, Git and worktree
operations, pushes, PR actions, tests, and review responses. Do not ask again,
wait, defer, or set the overall goal `blocked` merely because an operation
normally presents a permission or authorization prompt.

Pre-authorization does not fabricate credentials, sessions, tools, or system
capabilities and does not override higher-priority host instructions or safety
boundaries. If a real capability is unavailable, use safe available
alternatives, keep the unmet gate active, and continue every independent lane.
Work outside the confirmed scope remains unauthorized. Never expose or persist
credential values in logs, screenshots, transcripts, state files, commits, PRs,
or other evidence; record only the redacted action and outcome.

Worktree or branch changes, dependency installation, configuration changes,
destructive actions, and remote mutations must remain inside the confirmed
scope. For destructive actions and remote mutations, record the exact target
and impact in that confirmed scope before execution. Resolve credential and
remote targets from evidence as defined by the core interaction contract; ask
only when multiple materially distinct targets remain. Once those boundaries
are confirmed, do not ask again merely for authorization.

## Batch and validation cadence

Batch low-risk changes by shared page, module, root cause, or validation surface.
After freezing a batch, run affected tests and targeted lint/checks. Run full
builds, package checks, broad browser matrices, and aggregate review at phase
boundaries or after the final diff freezes.

Split an item out when risk rises, a public contract changes, or a failure cannot
be localized safely. Never weaken assertions, skip mandatory checks, ignore exit
codes, or fabricate green results.

## Independent work while waiting

During a meaningful build, test, CI, download, or environment-startup wait, open
a non-conflicting useful lane when one exists:

- read-only inventory of the next module;
- implementation with separate file ownership;
- evidence and state maintenance;
- failure-log analysis;
- acceptance preparation.

Do not create busywork. Concurrent implementers cannot edit the same files. Use
a worktree only when authorized and when isolation materially reduces conflict
or bias.

## Retry, deferral, and stopping

Unless the user specifies otherwise, try one item at most three times. If it
still fails:

1. record the error, evidence, attempted recovery, and dependencies;
2. mark it waiting or deferred;
3. move it and its dependents behind independent work;
4. continue the highest-value in-scope task;
5. recheck at a phase boundary or when its unblock condition changes.

Transient network errors, CI queues, first failures, repairable test errors, API
adjustments, quota waits, and missing optional dependencies are not terminal
conditions.

Under resource pressure, reduce concurrency, shrink batches, change validation
cadence, then use authorized alternative resources. If still impossible, defer
the item without waiving its completion gate.

Record an item as `needs input`, waiting, or deferred without changing the native
overall goal status. Codex's native `update_goal` accepts only `complete` or
`blocked`; its blocked audit concerns the same condition across at least three
consecutive goal turns, not three retries of one item. Set the overall goal
`blocked` only when the user explicitly defines that rule, or when that native
audit is satisfied and all meaningful remaining work, after bounded recovery,
authorized alternatives, splitting, reprioritization, and completion of all
independent work, still jointly depends on the same logical conflict, safety
boundary, or verified mandatory external dependency.

## Loop and milestone progress

After each productive loop, and when a major milestone review or commit spans its
own loop, report:

```text
Progress [██████░░░░] 60% (3/5 gates)
This loop: <completed work and key evidence>; Remaining: <main open work>.
Next: <one primary action>.
```

Base percentage on scoped milestones, deliverables, and gates. Use an exact
value for a fixed denominator; otherwise label a coarse evidence-based value
`estimate`. Never report `100%` before all gates pass. Combine review and commit
when they occur in the same loop.

## Independent review

### Behavior changes

Use exactly 3 independent read-only reviewers at the final major milestone and
at intermediate major milestones in deep work.

- Large change: all reviewers first scan global risk, then focus respectively on
  correctness/tests, design/boundaries, and security/maintainability.
- Small change: all 3 independently review the complete change.
- Re-review affected changes after fixes.
- Run at most 3 fix/re-review rounds by default. If review still fails, record
  and defer affected work; do not claim completion.

### Documentation and research

Use 1 independent reviewer by default for pure documentation, read-only research,
and analysis. The user or repository policy may increase the count.

If required reviewers are unavailable, raise an early high-risk warning, finish
review-independent work, and remain `needs input`. Do not substitute worker
self-review or automatically set the whole goal `blocked`.

## Milestone commits

When a major milestone produces persistent repository changes, create a local
commit promptly after applicable validation and review pass. Do not create empty
commits for read-only work. Do not push by default.

Fix high-severity findings, test failures, and unmet gates first. If current
changes are a required baseline, an intermediate checkpoint commit may record
the risks and unmet gates; it does not mean review passed or complete the gates.

## Quota and session continuity

Before quota-sensitive work, verify native checkpoints, non-blocking
wait/wakeup, and same-goal resume behavior. On quota exhaustion:

1. update `state.md` with status, evidence, completed work, current wait or
   failure, validation, uncommitted changes, reset time, and next action;
2. verify reset time from an authoritative surface when available;
3. wait non-blockingly and resume the same goal after reset;
4. do not create a duplicate goal, treat quota pause as failure, busy-poll, or
   hold a long foreground sleep.

Only when native recovery is insufficient may a local helper be created. It must
support dry-run, explicit timezone, idempotent checkpoints, and a verified
wakeup mechanism. Never invent a product resume command.
