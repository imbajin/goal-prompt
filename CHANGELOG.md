# Changelog

All notable changes to this project are documented in this file.

## 1.1 · 📅 2026-08-03

- Add fast and deep modes so focused tasks stay lightweight while long-running
  work gets resumable state and explicit recovery rules.
- Reuse existing requirements, designs, specs, and TODOs as active truth instead
  of generating duplicate planning files.
- Honor explicit requests to skip investigation or confirmation, allow users to
  delegate judgment, and keep unknown facts visible instead of inventing them.
- Keep work active through recoverable failures, waits, and permission gaps;
  declare the whole goal blocked only when all meaningful remaining work is
  jointly blocked.
- Scale independent review to the task: one reviewer for focused low-risk
  changes and three for deep or major behavior changes, with re-review after
  fixes.
- Add evidence-based loop progress and milestone commit rules without pushing
  by default.
- Move the installable Skill to `skills/goal-prompt/` so repository maintenance
  files and the full `skill-up` regression suite are not installed at runtime.
- Bundle only the runtime references, agent metadata, and public basic evals.
- Keep the full regression suite under `evals/skill-up/`.

## 1.0 · 📅 2026-07-25

- Publish the two-stage research, confirmation, and rendering workflow.
- Add scenario guidance and long-running goal execution references.
- Require conjunctive completion gates and blocked-work reprioritization.
- Support automatic selection and manual invocation in both Codex and Claude Code.
- Add Codex UI metadata while keeping the core skill portable.
