# Goal-prompt evolution TODO

Item-level status lives here. Valid states are `pending`, `in progress`,
`waiting`, `needs input`, `deferred`, and `complete`.

## P0: Freeze and preflight

- [x] GP-001 `complete` — Preserve the current dirty Skill and evaluation suite
  as an ordinary-file snapshot under `.eval-work/`; record hashes, diff
  manifest, commands, environment, and result locations without overwriting
  existing artifacts.
- [ ] GP-002 `needs input` — Reproduce one deterministic and one model-backed case
  with local skill-up 0.9.0 and the repository-pinned 0.7.0. Decide and record
  the authoritative execution version before full regression. The pinned
  0.7.0 binary is absent; installing it needs an explicitly named target.
- [x] GP-003 `complete` — Run the repository-observed static gates:
  `skill-up validate evals/skill-up/eval.yaml`,
  `bash -n evals/skill-up/fixtures/scripts/*.sh`,
  `bash evals/skill-up/fixtures/scripts/test-judges.sh`, and
  `git diff --check`.

## P1: Coverage and Judge quality

- [x] GP-101 `complete` — Build the behavior/risk/case/Judge/evidence coverage
  map from the current source and 28 cases.
- [x] GP-102 `complete` — Verify the new contract checker and shell wrappers
  against positive, negative, equivalent-wording, and missing-contract
  fixtures; preserve existing negation guards.
- [x] GP-103 `complete` — Adopt `check-goal-contract.py --root` as the formal
  artifact gate; it validates exactly one `state.md` and has positive,
  incomplete-state, and missing-contract fixtures.
- [x] GP-104 `complete` — Audit cases and Judges for duplicated coverage,
  contradictory expectations, hidden implementation wording, and weak
  false-green protection.

## P2: Current baseline and diagnosis

- [x] GP-201 `complete` — Run the current 28-case with_skill/without_skill
  baseline under frozen identical parameters and save JSON, HTML, transcripts,
  timing, token use, and exact commands.
- [x] GP-202 `complete` — Classify every FAIL/ERROR using the six-category
  taxonomy in `state.md`; inspect without_skill evidence before claiming
  incremental value.
- [x] GP-203 `complete` — Re-evaluate `deep-compression-gates` for loss of the
  global stop condition.
- [x] GP-204 `complete` — Re-evaluate `repository-rule-conflict` for explicit
  compatibility, safety, validation, and authorization risk.
- [x] GP-205 `complete` — Check whether compaction, parallel-agent, and UI
  Judges reject valid equivalent phrasing. Deterministic fixtures and post-hoc
  replay of the affected run cover the observed equivalent wording; remaining
  UI variability is model/case behavior, not a Judge false-red.

## P3: Evidence-driven improvement

- [x] GP-301 `complete` — For each confirmed Skill defect, add or preserve a
  failing regression, make the smallest single-owner change, and run affected
  cases three times.
- [x] GP-302 `complete` — Repair confirmed Judge defects only at the Judge layer
  and prove both false-red and false-green behavior with fixtures.
- [x] GP-303 `complete` — Repair invalid cases only when they contradict
  confirmed behavior; retain the previous wording and evidence in the run
  artifacts.
- [x] GP-304 `complete` — Inventory duplicated or misplaced Skill rules and
  refactor only after protected behavior is stable. Prefer existing references
  and one source of truth.
- [x] GP-305 `complete` — Final milestone used three independent read-only
  reviewers, applied and re-reviewed findings, then created local commit
  the current local milestone without pushing.

## P4: Final proof

- [ ] GP-401 `deferred` — Deterministic and high-risk gates are 100%; the
  `research-brief-boundary` model wording sample is 1/3 and remains a flaky
  TODO without a reproducible Skill defect.
- [ ] GP-402 `deferred` — The previous frozen candidate produced 43 PASS / 13
  classified FAIL / 0 ERROR, but its copied target SHA was not the final
  worktree. A fresh current-SHA run was attempted and stopped after Codex
  chronicle/unfinished-goal infrastructure errors without a complete report;
  re-run in a clean runner session before closing this gate.
- [ ] GP-403 `pending` — Execute 2-3 representative Codex tasks covering a fast
  change, deep recovery/refactor, and one high-risk boundary such as parallel or
  UI work. Fast and audit tasks are valid; deep task implementation/tests pass,
  but its independent-review and commit gates remain unverified due the fixture
  `.git/index.lock` permission boundary.
- [ ] GP-404 `pending` — Verify installable package contents, repository static
  checks, and CI.
- [x] GP-405 `complete` — Final three-lane review and re-review completed;
  evidence state was updated and the current local milestone was created. No
  push.
- [ ] GP-406 `pending` — Record live Claude Code validation as a scoped TODO
  unless separately authorized and available.
