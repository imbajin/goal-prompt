# Goal-prompt evolution TODO

Item-level status lives here. Valid states are `pending`, `in progress`,
`waiting`, `needs input`, `deferred`, and `complete`.

## P0: Freeze and preflight

- [x] GP-001 `complete` — Preserve the current dirty Skill and evaluation suite
  as an ordinary-file snapshot under `.eval-work/`; record hashes, diff
  manifest, commands, environment, and result locations without overwriting
  existing artifacts.
- [x] GP-002 `complete` — Reproduced a deterministic case with local
  skill-up 0.9.0 and the exact repository-pinned 0.7.0 installer, plus a
  model-backed `parallel-agents-goal` sample under identical wrapper/clean-home
  parameters; both versions passed 2/2 after the current Judge correction.
  Exact artifacts are under `.eval-work/p0-20260818T012626/version-sample/`;
  the CI-local replay also verified the pinned installer SHA and `v0.7.0`.
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
- [x] GP-402 `complete` — The current-SHA clean-home full run completed with
  56 units: 30 PASS / 22 FAIL / 4 ERROR; with_skill 21/28/0 and without_skill
  9/15/4. All errors were without_skill continuation timeouts. Every failure
  is classified in `state.md`, and all saved deterministic scripts were
  replayed through the corrected Judges in
  `final-full-clean-home-20260818T063409/replay-corrected.md`.
- [x] GP-403 `complete` — Executed fast, audit, and deep isolated Codex tasks.
  The deep export task finished at local commit
  `3ac0af16cc319a7f2cf4e1b5e18ea0fc5a4d8e98`; its temporary-workspace tests,
  recovery state, and three independent final read-only reviewers
  (`correctness-tests-r6`, `design-boundary-r6`, `security-maintainability-r6`)
  all pass. Earlier lock/reviewer failures are retained as historical evidence.
- [x] GP-404 `complete` — Exact CI-local replay passed package installation,
  JSON/metadata/readme hygiene, shell syntax, Judge fixtures, `git diff
  --check`, and pinned `skill-up v0.7.0` download/SHA/validation. Live Actions
  was not run; the local replay is the recorded CI-equivalent evidence.
- [x] GP-405 `complete` — Final three-lane review and re-review completed;
  evidence state was updated and the current local milestone was created. No
  push.
- [ ] GP-406 `pending` — Live Claude Code validation remains a scoped TODO;
  static compatibility checks are complete, but live Claude execution was
  explicitly excluded and needs separate authorization plus an available
  Claude runtime.
