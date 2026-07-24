# Long-Goal Execution Loop

Use this contract only for complex goals with remote CI, slow validation,
external environments, or cross-quota/session continuity needs. Put applicable
details in the selected live-state file; keep the `/goal` prompt compact.

## State ownership

Default to one `.goal-task/<task-slug>/state.md` containing phases, checkable
work, priority, current phase, validation evidence, blockers, recovery state,
environment identifiers, resume entrypoint, and next action. Existing specs or
designs remain separate when they are independently authoritative.

Split state only when a section has a distinct lifecycle, authority, size, or
audience. For example, a large audit report may hold evidence while `state.md`
links to it. A learning file is optional and never holds live status.

At initialization, audit the current revision and existing artifacts once. Mark
the active baseline in live state, replace or archive stale drafts, and remove
obsolete paths from the active truth list. Subsequent iterations read the active
truth, not every historical initialization artifact.

## Batch and validation cadence

Group low-risk fixes that share a page, module, root cause, or validation surface.
Run affected tests and scoped lint/checks after the batch freezes. Run full builds,
release-package checks, broad browser matrices, and aggregate review at phase
boundaries or after the final diff freezes. Split an item out when risk grows, a
public contract changes, or a failure can no longer be localized safely.

## Parallel waits

When a build, test, CI run, download, or environment startup is expected to take
more than two minutes, start a useful non-conflicting lane when one exists. Good
lanes include the next read-only inventory, another module with separate file
ownership, evidence/status maintenance, failure-log analysis, or acceptance
preparation. Do not create busywork. Concurrent implementers must not edit the
same files; use a worktree only when isolation materially reduces conflict or
bias, not by default.

## CI and external failures

A queue, first failure, transient network error, service startup failure, or
actionable test failure is not a terminal blocker. Record it, preserve evidence,
retry finitely with backoff when transient, diagnose or fix it, and continue other
scoped work. Never weaken assertions, skip required checks, ignore exit codes, or
fake responses to obtain green. Required gates must genuinely pass before the
goal completes.

When one task remains blocked, record its evidence and dependencies in live
state, move it and its dependent tasks behind independent unblocked tasks, and
continue the highest-priority work that can still produce goal evidence.
Re-evaluate deferred tasks at phase boundaries or when their unblock condition
changes.

Pause only after bounded recovery and reprioritization show that every meaningful
remaining task depends on the same unavailable external requirement or on a user
decision that cannot be made safely from existing scope. State the evidence,
completed work, deferred tasks, and exact condition that would unblock the goal.

## Connector and environment preflight

Before an expensive phase, verify only the connectors, credentials, environments,
and wakeup capabilities that phase needs. Record a safe fallback when one exists.
Do not treat an optional connector failure as fatal when an authorized CLI, API,
or local path provides equivalent evidence.

## Quota and session continuity

Before quota-sensitive work, verify native checkpoint, non-blocking wait/wakeup,
and same-goal resume behavior. On quota exhaustion:

1. update live state with task status, evidence links, completed work, current
   failure or wait, validation results, uncommitted changes, reset time, and the
   next action;
2. verify reset time from the authoritative surface when available;
3. use a non-blocking wait and resume the same goal after reset;
4. do not create a duplicate goal, mark the quota pause as failure, busy-loop, or
   hold an interactive foreground sleep.

Only if native recovery is insufficient may the goal create a local helper. It
must support dry-run, explicit timezone handling, idempotent checkpoints, and a
verified wakeup mechanism; it must not invent a product resume command.
