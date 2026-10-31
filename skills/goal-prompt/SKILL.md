---
name: goal-prompt
description: Create, rewrite, shorten, or review /goal prompts for Codex, Claude Code, and other coding agents. Use only when the user explicitly requests /goal text or asks to convert a task into /goal; never start the goal automatically.
---

# Goal Prompt for Codex and Claude Code

Produce a verifiable, persistent goal prompt. Investigate, confirm the outcome
and initialization plan, prepare approved Markdown files, then render the prompt.
Do not start or execute the goal. An ordinary implementation request does not
invoke this workflow.

## Routing and authorization

Classify the request using this table; explicit Stage 2 routes override the
pending-confirmation default. User instructions override Skill defaults;
higher-priority host instructions and safety boundaries still govern.

| State | Required response |
| --- | --- |
| Outcome, scope, or initialization not confirmed | Stage 1 brief, material questions, then stop and wait |
| Explicit confirmation, explicit confirmation skip, or delegated remaining judgment | Investigate as applicable, then Stage 2 |
| User asks for a final goal from approved materials that already settle outcome and scope | Stage 2; choose the minimum mode/initialization without re-confirming; keep unknown facts |
| Ordinary work rather than goal text | Do not turn it into goal-backed work |

A first-turn request to create a goal, or the word “final” alone, is not
confirmation. Do not infer approval from silence, sufficient evidence, or a
request to continue before a brief exists. Semantic confirmation is enough;
no fixed status string is required. Approved-materials authorization includes
choosing the appropriate mode and creating its minimum necessary state file. A later change that explicitly authorizes
the new scope proceeds; otherwise confirm material changes again.

“Generate directly” skips confirmation, not investigation. Skip investigation
only when explicitly requested. Delegated judgment means investigate, choose,
and continue without another preference question. If both investigation and
confirmation are explicitly skipped, render immediately, keep unavailable facts
unknown, and omit unverified paths and commands.

In every final goal, make resolution of material unknowns an execution gate before
dependent actions. Continue independent work; ask only when the missing fact
changes the objective or makes a safe goal impossible.

### In-scope operations

All user-authorizable actions needed inside the confirmed scope are
pre-authorized, including Chrome uploads, entry of already available credentials,
file/dependency/environment changes, worktrees and Git operations, pushes, PRs,
tests, and review responses. Do not ask again, wait, defer, or mark work
`blocked` merely because such an action normally needs authorization. Out-of-scope
actions remain unauthorized. This authorizes later execution and approved
initialization; it does not authorize this Skill to implement or start the goal.

Resolve operation targets from evidence: identify the account/environment and
purpose for credentials, and the repository/remote/branch/PR for remote writes.
Record a single supported target without asking. Ask a scope question only when
multiple materially different targets remain and the user has not delegated the
choice. Record destructive or remote targets and impact before execution.

Never fabricate credentials, sessions, tools, or capabilities, or override
higher-priority safety boundaries. Never expose, echo, screenshot, transcribe,
persist, commit, or publish credential values; keep credential-bearing UI out of
evidence. Record only redacted actions and outcomes. For a real capability gap,
keep its gate open, use safe alternatives, and continue independent work.

The final goal must include the in-scope pre-authorization and capability/safety
boundary explicitly; a reference to state.md alone is insufficient.

## Stage 1: investigate and confirm

### Investigate relevant context

Read user-provided paths, specs, decisions and available repository guidance,
including the nearest AGENTS.md and contributor rules. Inspect the current
worktree, relevant implementation/callers/tests, package scripts and CI. Verify
remote or changing facts live. Stop when further inspection would not change
the outcome, mode, evidence, or material questions; do not inventory mechanically.

Establish the desired after-state, current gap, scope/exclusions/invariants,
real validators, authority order and unresolved dependencies. When reviewing or
rewriting a draft, check both observable results and evidence for its full scope;
activity words or tests alone do not prove behavior, migration, documentation,
deployment and review requirements.

Do not invent paths, commands, dependencies, metrics or repository facts. Missing
context still permits a bounded brief with honest unknowns, a result/scope/evidence
framework and a confirmation request. Distinguish evidence gaps from user choices.
Ask only questions that materially change the goal and cannot be resolved from
evidence, a safe reversible assumption, or authorized delegated judgment.

Preflight only capabilities the task may need: writes, commands, network,
subagents, Git, connectors and wakeup. State any actual gap, affected phase and
safe alternative; do not recheck already granted authorization.

### Select mode and guidance

| Mode | Use and initialization |
| --- | --- |
| Fast | Focused, low-risk work that fits one validation cycle; no sidecar by default; state.md only for real continuity needs |
| Deep | Multiple subsystems/phases, public compatibility/migration boundaries, remote waits, cross-session recovery, or durable checkpoint/resume/idempotency/replay/rollback; always non-empty state.md |

Recommend a mode for confirmation unless already selected or delegated. Keep a
confirmed deep mode even when the final prompt is short. Complexity alone does
not require more files.

Read only the matching section in `references/scenarios.md`. Also read:

- `references/long-goal-execution.md` for deep, long-running or durable recovery work;
- `references/parallel-agents.md` for genuinely independent parallel lanes;
- `references/ui-acceptance.md` for frontend/UI work;
- `references/long-goal-learning.md` only when selecting a learning record.

### Choose truth files

Reuse approved specs, designs and task files rather than duplicating them.
New initialization files belong under `.goal-task/<task-slug>/`:

| File | Responsibility and trigger |
| --- | --- |
| state.md | Execution contract, current baseline, active-truth index, phases/gate evidence, recovery and next action; required in deep mode |
| todo.md | Large or frequently changing item list; sole owner of item-level status/waits when present |
| design.md | Material durable decisions/interfaces/invariants lacking an authoritative existing design |
| lessons.md | Evidence-backed reusable lessons; never an empty placeholder; fast mode only after a concrete failure or user request |

Do not create goal.md, progress.md, blockers.md or duplicate decisions files.
A required formal report may use its own artifact path. State indexes rather
than copies specs, full TODOs and lessons. Put unfinished one-time preparation in
state's Initialization TODO; after completion retain only relevant results.
Within task materials use latest user confirmation > authoritative spec/design >
issue/todo > state. Host instruction priority always applies.

### Stage 1: confirmation brief

Start with `Proposed goal brief`. Do not write the literal slash-goal command,
a copyable goal, or language presenting one as ready in this response. Include:

- outcome, scope/exclusions and conjunctive completion evidence;
- recommended mode and reason, existing truth paths, and each proposed new file's purpose;
- initialization actions, resolved operation targets/impact and actual capability gaps;
- material open assumptions/questions, followed by a semantic confirmation request.

Preserve exact interface keys, ordering, checkpoint timing, compatibility rules
and observed validator command strings when they are material; do not compress
them into “preserve behavior” or “all scripts pass”. Cite repository policy files
by exact name. For user-requested overrides, name each overridden rule and
its concrete consequence in the current response, not a promise to explain later
(e.g. removed export breaks callers, new dependency adds maintenance/security
surface, skipped typecheck leaves a verification gap).
For research, separate labeled `Evidence gaps` and `Preference gaps`, writing
`none` for an empty list; connect comparison dimensions to the decision and real
citations. For gatekeeper review, require severity, exact location, observed
evidence and recommendation for every finding, even when the target is missing.

For deep behavior/migration work, name the reviewer count and re-review gate,
checkpoints/retries and concrete independent work during waits. Explicitly state
that waiting/deferred/needs-input items move behind independent work and that
overall blocked requires all remaining work to share a real blocker and satisfy
host status rules. A read-only report uses evidence review, not implementation
gates. End the brief and wait unless routing already authorizes Stage 2.

## Stage 2: prepare and render

In approved deep mode, create/refresh non-empty state.md and only the additional
files whose triggers apply. Perform approved one-time environment preparation;
do not begin implementation. Verify referenced paths, remove stale drafts from
active truth, and record unfinished preparation for later execution. Fast mode
normally needs no files. When investigation was explicitly skipped, omit
unverified paths instead of pretending initialization occurred.

Use `references/long-goal-execution.md` for the full deep execution contract.
Preserve the user's explicit progress/reporting format in the final goal and any
execution contract. If a requested percentage lacks a verified fixed denominator,
retain the other fields and state why it cannot yet be quantified.
Fast goals carry their applicable compact rules inline: at most three attempts
per item before deferring/reordering behind independent work; visible completed
and remaining work plus one next action after productive loops; one independent
reviewer for focused low-risk behavior changes and re-review after fixes;
validation/review before local commits, no empty commits and no push by default.
Fast goals must also carry the current host's cross-turn blocked audit (the same
blocker for three consecutive goal turns when required, distinct from per-item
retries), and require no unresolved high-severity finding before completion.
Preserve a user's explicit reviewer count. Deep behavior/migration goals and their
state must require independent review at major behavior-change milestones as
well as final integration; final-only review is insufficient.

Render one Markdown code block containing the final goal, followed only by a
short explanation of mode, initialization files and grounded tradeoffs. Include:

1. The confirmed observable outcome, scope/exclusions and minimum active-truth paths.
2. Explicit inline pre-authorization, credential/capability/safety boundaries and
   continuation of independent work; resolve material unknowns before dependent actions.
3. Conjunctive completion gates covering actual behavior, real validators,
   compatibility/invariants, documentation and applicable independent review/re-review,
   with no unresolved high-severity findings.
4. Persistence/reordering and exceptional stop conditions: all meaningful remaining
   work jointly blocked after recovery, with the current host's status rules satisfied.
5. For deep mode, the verified state.md entrypoint holding detailed execution,
   checkpoints, retries, review and commit rules. Its loop contract must briefly
   assess each productive loop's results and use that assessment to retain or
   adjust the next action; this feedback does not require a learning file.
6. The user's explicit reporting format, without inventing percentages when a
   verified fixed denominator is unavailable.

For UI goals require real Chrome `browser_use` or its available equivalent,
functional success/failure interactions and UI/UX/accessibility evidence; follow
the UI reference. For research/audit keep read-only boundaries and evidence gaps.
Do not claim that generating the goal proves its execution.

Keep fast goals near 450 tokens and deep goals near 700 when practical. Unless
the consuming harness is known to allow more, the rendered goal must be shorter
than 4000 Unicode characters. Preserve material facts, decisions, caveats, next
actions and every gate; trim repetition and optional background first. Move deep
detail into state without creating files solely to save length. Include a token
budget only when the user requested it.

### Stage 2: final `/goal`

```text
/goal <observable confirmed outcome>.

Active truth: <verified paths; deep mode: state.md execution/recovery entrypoint>.
Scope: <included work and exclusions>.
Resolve material unknowns before dependent actions; continue independent work.

All user-authorizable actions required within the confirmed task scope are
pre-authorized, including Chrome uploads, entering available credentials,
file/dependency/environment/Git changes, pushes, PRs, tests and review responses.
Do not ask again or stop, wait, defer or mark blocked because of authorization.
This does not fabricate credentials, sessions, tools or capabilities, override
higher-priority safety boundaries, or authorize out-of-scope work. Never expose
or persist credential values. Use safe alternatives and continue independent work
when a real capability is unavailable, keeping its unmet gate active.

Execution: <fast inline rules, or deep state.md contract reference; preserve the
user's reporting format, with percentages only for a verified fixed denominator>.
Complete only when all apply:
1. <observable result and material invariants>.
2. <real validators and evidence for the full scope>.
3. <documentation, independent review count and re-review after fixes as applicable>;
   no unresolved high-severity findings.

Overall blocked requires all meaningful remaining work to share a verified
blocker after recovery/reordering and the current host's status rules to be met.
```
