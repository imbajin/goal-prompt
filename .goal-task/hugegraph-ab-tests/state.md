# HugeGraph A/B tests — live state

Last verified: 2026-08-20 Asia/Shanghai

## Objective

Add a separate two-stage A/B suite to this `goal-prompt` repository, using one representative frontend, backend, and documentation task from the Apache HugeGraph canonical repositories. The suite must compare the same raw request with and without `goal-prompt`, then execute the generated prompts in isolated fixtures and score real behavior.

## Active truth order

1. User-provided repository instructions in the current task.
2. `docs/hugegraph-ab-test-plan.zh-CN.md` — researched decisions, versions, rubrics, phases, and exclusions.
3. `docs/hugegraph-ab-test-prompts.zh-CN.md` — component implementation/run prompts and exact Raw Requests.
4. This file — current progress, evidence, blockers, and next action.
5. `docs/hugegraph-ab-test-single-goal.zh-CN.md` — consolidated entrypoint generated earlier; it must not override the three active-truth files above.
6. Existing `evals/skill-up/README.md`, `evals/skill-up/eval.yaml`, and repository tests.

Do not create `goal.md`, `todo.md`, or `design.md` that duplicates these files.

## Current phase

| Phase | Status | Evidence / exit condition |
| --- | --- | --- |
| Research canonical repositories | complete | Three parallel read-only investigations plus primary-source verification |
| Select representative cases | complete | Frontend #486, backend #3095, docs Graphs API version truth |
| Define A/B protocol and rubrics | complete | Detailed plan and prompts documents |
| Independent documentation review | complete | One read-only reviewer found 3 P1 and 2 P2 issues in the detailed documents; all were closed, and the same reviewer then approved the consolidated single Goal with no findings |
| Implement suite | complete | Three cases/rubrics, bound preflight/fixtures, independent Prompt arms, tracked rebuildable runtime, per-arm service/network/data isolation, Agent/trusted artifact separation, container-isolated behavior oracles, critical-aware judges, preregistered cohort summary, and deterministic fakes exist; exactly three final reviewers report no unresolved P0/P1 on the frozen diff |
| Deterministic validation | complete for current diff | Fake two-stage smoke, prompt/error retention, evidence/score binding, sealed Pilot/Formal schedules, failure classification, version-drift/source-evidence, FIFO secret delivery, interrupt/process-group/service cleanup, judge and existing regression checks pass at `self-test-32984` |
| Real Pilot | infrastructure ready; credentials/control-plane input required | Three online active/no-drift preflights completed, the 3-pair Pilot cohort is sealed, reviewed executor/oracle images build and pass runtime probes, and full deterministic validation passes; no model A/B arm has run yet |
| Formal 3-pair experiment | not started | No results exist |

## Verified version facts

| Repository | Verified refs | 1.8 statement |
| --- | --- | --- |
| `apache/hugegraph-toolchain` | official 1.5.0 and 1.7.0 tags/releases; current master is a moving development line | Root POM labels the development line 1.8.0, but there is no formal 1.8 tag/release and its HugeGraph dependency remains 1.7.0 |
| `apache/hugegraph` | official 1.5.0 and 1.7.0 tags/releases; master is post-1.7 | No 1.8 tag/release/release branch; master POM was still 1.7.0 at verification time |
| `apache/hugegraph-doc` | release-1.5.0 branch, 1.7.0 tag/release, rolling master | No 1.8 ref; do not invent one |

All `master` claims require a fresh preflight. Published refs use their names. Do not add a checked-in commit hash; resolve each moving ref once per pair and record it only in `.eval-work/` metadata.

## Decisions that must remain true

- Main A/B variable: `goal-prompt` absent vs present during prompt generation; raw task is byte-identical.
- Downstream execution uses the same executor/config and a fresh, identical fixture for each arm.
- The primary outcome is behavior score and critical-failure rate, not prose length.
- Prompt quality, tokens, time, turns, and completion rate are explanatory/secondary metrics.
- Main cases:
  - Toolchain: empty-graph first vertex plus missing nullable-property edit.
  - Server: HStore isolation with both direct REST graphspace/graph/store smoke and focused store-core PUT/MERGE/doGet/truncate/rollback/concurrency coverage.
  - Docs: bilingual Graphs REST API version truth and executable examples.
- Modifiable working source and an identical read-only version-evidence manifest must enter each execution workspace; public issue/PR answers, `.git` history, judges, and variant labels must not.
- No new source hash, frozen output format, checked-in golden/history benchmark, persistent model result, or CI/merge enforcement.
- Paired with/without-Skill comparison is explicit and transient; suite config stays disabled by default. Prompt roles run as two independent single-role configs in an explicitly balanced order and do not create a persistent benchmark.
- Upstream stale behavior is classified as `stale`, not as an A/B failure.
- No push or MR.

## Execution loop

1. Read the active truth and current repository state.
2. Do the next smallest phase that creates verifiable progress.
3. Update this file with commands, results, blockers, and the next action.
4. For a failing item, try at most three evidence-based approaches; continue independent work meanwhile.
5. Mark blocked only when all meaningful remaining mainline work depends on the same unresolved external condition.
6. For behavior-changing suite code, finish with exactly three independent reviewers:
   - A/B causal design and isolation;
   - HugeGraph source/version accuracy;
   - scripts, judges, safety, and deterministic tests.
7. Fix all high-severity findings, rerun affected validation, then make a local commit using repository rules. Do not push.

## Mainline acceptance conditions for suite implementation

- Separate suite exists without changing the current fast suite's behavior.
- `skill-up validate` and dry-run pass for all three cases.
- Fixture preparation proves A/B source identity and workspace/HOME/session/data isolation.
- The prompt phase sends byte-identical raw requests to both variants.
- The execution wrapper passes each generated response verbatim without requiring a fixed JSON/heading format.
- Preflight detects canonical/version drift and stale cases.
- Rubrics enforce the documented hard failures and score behavior, not expected patches.
- Synthetic judge tests reject visual-only frontend fixes, store-core-only results claiming full REST isolation, mock-only backend fixes, one-language docs, and false 1.8 claims.
- Fake generator/executor smoke proves the two-stage flow without real model cost or answer leakage.
- Existing repository validation remains green.
- Three final reviewers have no unresolved high-severity findings.

## Mainline acceptance conditions for real experiment

- Pilot: one clean pair for each of the three cases.
- Formal: three clean pairs for each case after Pilot is healthy.
- Every run records raw task score, critical failures, prompt score, completion, tokens, time, turns, and retries.
- Variant identity is blinded for scoring and revealed only after scoring.
- Report includes every pair, per-case deltas, medians, win/tie/loss, costs, limitations, stale/excluded runs, and no statistical-significance claim.
- One independent analysis reviewer verifies the mapping and calculations when no behavior code changed; use three final reviewers if suite behavior changed during the run.

## Current evidence

| Check | Result |
| --- | --- |
| Current repo branch before docs | clean `master` tracking `origin/master` |
| Existing eval | Prompt-level skill-up suite already supports with/without-Skill comparison |
| Existing limitation | `evals/skill-up/README.md` explicitly says generated `/goal` is not an end-to-end task proof |
| Tool availability | Repository-pinned `skill-up 0.7.0` is temporarily available under `.eval-work/tools`; checked-in config validates. The suite does not rely on its fixed benchmark order: it materializes two independent one-role configs and records explicit Prompt order/model/reasoning/budgets |
| Network research | Canonical releases, issues, draft/merged PRs, source files, and docs pages were checked on 2026-08-19 |
| Upstream writes | none |
| Model A/B calls | none |
| Pilot preflight | Three fresh canonical checkouts; Toolchain master, Server 1.7.0, and Docs master all classified `active`, `online`, and no version drift. A transient matching-Server partial-clone blob failure was recovered by fetching commit-addressed raw blobs and verifying their Git object IDs |
| Pilot cohort | `pilot-20260820-live-01` is sealed with three pairs; Prompt and execution first-role schedules are independently 2/1 balanced |
| Runtime capability | Docker Desktop is healthy with 8 GiB RAM. Reviewed executor/oracle images build from the exact active preflight sources. Codex 0.147.0, Hugo Extended 0.102.3, Yarn 1.22.22, Maven 3.9.9, offline dependency trees, trusted JUnit/Hamcrest, and an actual headless Chromium launch all pass inside the images; executor/oracle asset separation and 0500/0400 oracle permissions were checked |
| Local delivery | Earlier scoped suite/docs commit `93e7c61` exists; the current validated runtime hardening is delivered as a separate local milestone commit on this branch; no push or MR |
| Independent suite review, final round | Exactly three read-only reviewers independently checked Backend, Toolchain/runtime, and Docs. All report no unresolved P0/P1 on the same frozen diff. One non-blocking P2 remains: targeted Jest's own summary is candidate-produced; real browser behavior is scored independently by the trusted Playwright path |
| New suite validate | `.eval-work/tools/skill-up-bin/skill-up validate evals/skill-up/hugegraph-ab/eval.yaml` loaded exactly 3 cases |
| Paired dry-run | Wrapper reported all 3 cases and checked config mode without invoking an Agent; pair-specific materialization is repeatable after a read-only fixture dry-run |
| Current deterministic rerun | `HG_AB_SKILL_UP="$PWD/.eval-work/tools/skill-up-bin/skill-up" bash evals/skill-up/hugegraph-ab/scripts/test-suite.sh` completed at `.eval-work/hugegraph-ab/self-test-12376` with `hugegraph-ab deterministic suite: PASS`; no model was invoked |
| Fake two-stage smoke | Current smoke passes and covers byte-identical Raw Requests, same-source/evidence copies, forged Agent score isolation, behavior-evidence binding, partial Prompt ERROR retention, model-failure zero score, blinded environment diagnostics, critical score zeroing, aggregate suppression, exact sealed Pilot/Formal schedules, per-pair snapshots, service network reuse rejection, FIFO secret non-persistence, SIGINT/SIGTERM process-group cleanup including a TERM-ignoring grandchild, cleanup failure sidecars, unexpected 1.8 drift, Toolchain `index.js` markers, and Docs auth fallback evidence |
| Real isolation contract | Real path now requires a reviewed per-arm service spec, unique internal network/data root, actual HTTP/TCP policy/health/CONNECT probe, checked executor/oracle images, Agent-only artifact mount, isolated oracle container and terminal cleanup. No real service/model was run in this suite-only Goal; Pilot must exercise the final contract before producing results |
| Existing regression | Existing deterministic judges and the existing 20-case `evals/skill-up/eval.yaml` validation pass |

## Blockers

The active Pilot cannot start Prompt arms until a reviewed OpenSandbox control-plane URL/template/attestation and `HG_AB_OPENSANDBOX_API_KEY` plus `HG_AB_PROMPT_MODEL_API_KEY` are available. Downstream arms also require `HG_AB_MODEL_API_KEY` and a mode-0600 credential-free `runtime-private.json` identifying the provider endpoint, fixed model, and policy. A 2026-08-20 recheck found all three variables, the private config, and the Prompt runtime attestation absent. The executor/oracle images are verified, but the real per-arm service/network/model-proxy isolation probe necessarily remains pending until those inputs exist.

## Next action

After the user configures the reviewed OpenSandbox URL/template/attestation, the three private credential variables, and the mode-0600 runtime-private config locally, run the real per-arm isolation probe. Then run all six Prompt arms and all six downstream Pilot arms without selective retry. Enter Formal only after the Pilot is healthy.

## Progress accounting

- Suite implementation milestone: 100%. Research, task selection, one-Goal entrypoint, implementation, deterministic validation, online preflight, sealed Pilot schedule, and three-reviewer P0/P1 closure are complete.
- Overall experiment: 48%. This percentage weights research/design/suite/preflight as 45%, real Pilot as 25%, Formal as 20%, and final analysis/report as 10%; the additional 3% is the completed real-runtime image build and probes within the Pilot phase. The next mainline task is the credentialed isolation probe followed by the real Pilot; no Prompt or downstream model arm has run yet.
