# Changelog

All notable changes to this project are documented in this file.

## 1.2 · 📅 2026-09-02

- Tighten the confirmation protocol so Stage 1 cannot leak a final goal and
  explicit delegation still proceeds without another approval round.
- Pre-authorize all in-scope user-authorizable actions while resolving the
  account, credential purpose, remote, branch, or PR target from evidence.
- Strengthen deep-work recovery, shared-file ownership, re-review, UI browser
  acceptance, and exceptional all-work-blocked semantics.
- Separate read-only research and audit goals from behavior-change workflows so
  they do not inherit implementation gates mechanically.
- Expand the `skill-up 0.9.1` suite to 30 cases, document the strict A/B
  isolation protocol, and harden deterministic Judges against false positives.

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
