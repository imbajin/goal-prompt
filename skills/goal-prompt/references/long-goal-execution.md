# Long-Goal Execution Loop

For deep, multi-phase, remote-wait or durable recovery work, put this contract
in `.goal-task/<task-slug>/state.md`; the final goal keeps its verified entrypoint
and conjunctive completion gates. Adapt native tool names to the current host;
Codex and Claude Code need not expose the same goal/status/wakeup mechanisms.

## State and checkpoints

Create a non-empty state.md with baseline revision/environment, active-truth
index/authority, phases/gate evidence, review/validation, dependencies/recovery,
next action and applicable execution rules. Reuse authoritative specs/designs.
Use todo.md only for a large/changing list; when present it alone owns item-level
status/waits, while state keeps counts and dependencies. Design and lessons files
have their own purposes, never duplicate daily status.

Before context compaction, quota wait or handoff, checkpoint completed/remaining
work, latest commit, uncommitted changes, validation/review evidence, active waits,
recovery conditions and one next action. Report a percentage only for a defined
denominator. Resume by checking state against the current checkout and evidence,
not by reconstructing conversation history. Recheck initialization only when
scope, baseline, design or environment materially changes. Remove completed
Initialization TODO steps, retaining relevant results or constraints.

## Authorization and capability

Use the in-scope pre-authorization, target resolution and credential safety
contract in SKILL.md; include it explicitly in the final goal. Preflight actual
write/command/network/subagent/Git/connector/wakeup capabilities once, naming any
real missing capability, affected gate and safe alternative. Authorization does
not create tools, credentials or sessions or override host rules. Keep unmet gates
open and continue independent work; do not re-ask authorization already granted.

## Batches, waits and retries

Batch by module, root cause or validation surface. Freeze a batch, run affected
tests/checks, then broader integration/package/browser gates at phase boundaries
or when a new concern warrants them. Preserve assertions, thresholds, exit codes
and honest evidence. Split high-risk or unlocalized failures from independent
work. A generated requirement or a historical green run is not current execution
proof.

During useful waits continue non-conflicting work such as the next module's
read-only inventory, separately owned implementation, evidence/state maintenance,
failure analysis or acceptance preparation. Do not invent busywork or let workers
write the same files; use the parallel reference when lanes are independent.

Unless the user specifies otherwise, try an item at most three times. Record
error/evidence/recovery/dependencies, mark the item waiting/deferred/needs input,
move it and dependents behind independent work, and recheck when its unblock
condition changes or at a phase boundary. This does not waive its completion gate.
First failures, queues, repairable tests, quota or optional dependency gaps do not
by themselves stop the overall goal. Under resource pressure reduce concurrency
and batch size or use authorized available alternatives.

Item retries and native goal status are separate. Follow the current host's
status contract; do not hard-code a tool's accepted status values or assume a
status API exists. In Codex, three retries in one turn do not satisfy a blocked
audit requiring the same blocker across consecutive goal turns. Overall blocked
requires both the host audit and all meaningful remaining work jointly depending
on the same verified mandatory external dependency, safety boundary or logical
conflict after recovery, alternatives and independent work are exhausted. A user
pause is handled under the host pause rule, never inferred from a quota wait.

## Progress, review and commits

After each productive loop report completed work with evidence, remaining gates
and one primary next action. Give a percentage only when the denominator is
clear, never 100% before all gates pass. After a milestone commit include the
commit and what is now complete. Keep item-level status in todo.md when present.

For deep/major behavior-change milestones use 3 independent read-only reviewers
by default; preserve the user's explicit count. All scan the integrated diff and
evidence, then large changes may split correctness/tests, design/boundaries and
security/maintainability. Implementers do not count as independent reviewers.
Fix findings and re-review affected changes; at most three fix/re-review rounds
by default, then defer unresolved work without claiming completion. Pure docs,
research and audit use 1 independent evidence reviewer unless otherwise required.
If reviewers are unavailable, finish review-independent work, record the unmet
gate and recovery condition; do not replace review with worker self-review.

Commit persistent milestones locally after applicable validation/review pass;
no empty commits or push by default. A necessary intermediate checkpoint may
record unmet gates explicitly, but cannot claim those gates passed. Never drop
high-severity findings or mandatory validators to create a milestone.

## Quota and session continuity

Before quota-sensitive work verify actual checkpoint, non-blocking wait/wakeup
and same-goal resume capabilities. Capacity/quotas and host pause behavior are
platform constraints, not things a Skill can repair or promise to control.
On exhaustion checkpoint state, current waits/failures, evidence, uncommitted
changes, a verified reset time if available, and the exact next action. Do not
invent a reset time, resume command or automatic wakeup.

Use native non-blocking recovery only when verified available. Otherwise retain
a manual resume entrypoint and unmet gates; continue independent work where
possible. Do not duplicate the goal, busy-poll or use long foreground sleeps.
Create a helper only if needed, authorized, and its dry-run, timezone,
idempotent checkpoints and real wakeup mechanism can all be verified.
