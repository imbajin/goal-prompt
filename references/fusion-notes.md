# Fusion Notes

This project combines design ideas from two references rather than copying
either one verbatim.

## Sources

- OpenAI `define-goal`:
  https://github.com/openai/skills/blob/main/skills/.curated/define-goal/SKILL.md
- `win4r/goal-prompt-builder`:
  https://github.com/win4r/goal-prompt-builder

## Retained

From OpenAI `define-goal`:

- concrete outcomes rather than activity descriptions;
- explicit verification evidence and honest quantitative or binary thresholds;
- bounded scope and detectable stop-and-ask conditions;
- clarification only when missing information could change the intended result;
- the prompt builder itself does not execute goals or manage runtime state.

From `goal-prompt-builder`:

- a copy-pasteable `/goal` artifact;
- Objective, Scope, Constraints, conjunctive completion gates, and exceptional
  stop conditions as the core reading flow;
- context-aware interaction adapted into one research-confirm-render flow;
- repository-context inspection and scenario-specific guidance;
- a brief explanation after the generated prompt.

## Modified

- The five-section structure is a compact control entrypoint, not a container for
  the complete implementation plan.
- Detailed requirements and TODOs move into source-of-truth Markdown files.
- Acceptance and stop-condition counts follow actual requirements instead of a
  fixed minimum or target range.
- Audit quality is `ready` or `needs confirmation`, not a numeric score.
- Project commands and constraints come from repository evidence instead of
  language-specific defaults.
- Token budgets are included only when the user explicitly requests or confirms
  one.

## Omitted

- mandatory token budgets and fixed budget ranges;
- hard-coded Codex versions, simulator names, test commands, or dependency bans;
- provider-specific invocation language;
- automatic network probing or automatic recommendation of a spec framework;
- automatic goal creation or direct creation of sidecar files;
- `.autonomous/` state semantics.

## Added locally

### Prompt length

- ordinary target: 12-25 lines and about 450 tokens or less;
- complex hard limit: about 700 tokens;
- detail beyond that limit moves to source-of-truth files.

### Sidecar documents

- source-of-truth selection is need-driven rather than complexity-count driven;
- ordinary goals use no sidecar by default;
- durable complex work defaults to one `.goal-task/<task-slug>/state.md`, with
  existing authoritative specs/designs and genuinely separate large reports
  added only when their lifecycle or authority differs;
- learning, decision, blocker, and progress files are optional rather than a
  mechanical minimum;
- the prompt builder itself does not create these files.

### Two-stage interaction and initialization

- the builder must investigate real context and present a disposable goal brief
  before it renders a final `/goal` prompt;
- explicit user confirmation of the core outcome, scope, and evidence separates
  research from finalization;
- the disposable brief is conversation context, not durable truth;
- when executor initialization is needed, the final prompt carries only a compact
  one-time baseline-refresh rule;
- stale initialization drafts are retired from the active truth list so later
  goal iterations do not repeatedly consume obsolete artifacts.

### Independent review

- behavior-changing code work requires a separate read-only reviewer subagent;
- the implementation worker cannot act as reviewer;
- fixes require independent re-review;
- an unavailable independent reviewer is a mandatory final blocker, not
  permission to self-review; finish review-independent work before stopping;
- pure documentation and read-only research do not require this gate by default.

### Progress reporting

- publish a compact progress bar after every milestone or meaningful phase
  boundary, not at arbitrary time intervals;
- keep it to three short lines: percentage, completed/remaining items, and one
  next primary action;
- derive percentages from scoped milestones, deliverables, and completion gates;
  use an exact value for a fixed denominator, otherwise label a coarse estimate;
- reserve `100%` for the point when every applicable completion gate passes.

### Completion and blocker semantics

- every applicable completion gate is required; satisfying one gate never ends a
  multi-gate goal;
- an item that cannot proceed is marked waiting or deferred and moved behind
  independent work; it does not make the overall goal blocked;
- the overall goal may be marked blocked only when all meaningful remaining work
  is impossible after bounded recovery, authorized alternatives,
  reprioritization, and completion of independent work.

### Long-goal execution and learning loops

- apply the extra machinery only to complex long-running goals, not ordinary
  tasks;
- treat CI, transient, API-adjustment, and quota blockers as resumable or
  deferrable work rather than terminal blockers;
- batch low-risk fixes by shared validation surface and use a two-minute threshold
  for useful non-conflicting parallel lanes;
- keep durable runtime state in the selected live-state file;
- add a learning file and promotion candidates only when the confirmed goal
  selects that deliverable, and require explicit user approval before changing
  AGENTS instructions or Memory.

These rules were added after long-running production work exposed premature CI
blocking, repeated small-scope validation, idle waits, and missing quota-resume
behavior. They are generalized around observable task properties rather than a
specific project.

The two-stage and minimal-truth rules were added after repeated use showed that a
single-pass renderer could skip investigation, avoid confirmation, overproduce
sidecars, and leak disposable initialization work into the enduring goal prompt.
