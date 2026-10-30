# Cache refactor execution and recovery state

## Confirmed outcome and authority

- Mode: Deep, because public API compatibility is a material boundary.
- User confirmed the proposed brief on 2026-10-30 and delegated remaining judgment without another confirmation.
- Outcome: improve the internal responsibilities and maintainability of the requested `src/cache` subsystem while preserving public exports, call signatures, types and observable behavior.
- Scope: cache internals, necessary caller investigation, regression coverage and directly relevant documentation. Exclude new features, unrelated module changes, and unapproved API, schema or dependency changes. Prefer existing implementation, native facilities and installed dependencies.
- Task truth order: latest user confirmation > verified authoritative repository specifications/designs > issue/item records > this state. Host instruction priority always applies. User-provided AGENTS.md instructions apply; repository policy paths are not yet known.
- Active truth: this file. The requested `src/cache` path is a scope description, not a verified source path in this workspace. Add actual repository truth paths only after verification; do not duplicate authoritative designs here.
- Integration owner: the executing primary agent. This goal preparation does not start implementation.

## Observed baseline and capability limits

- Preparation workspace: `/private/var/folders/sx/1999c8sj0bv26zt9kgxcp7wr0000gn/T/skill-up-3562154274`.
- Initial inspection found only `.codex` at workspace root. No project source, cache callers, tests, package scripts, CI, contributor rules or repository AGENTS.md were available. `git status --short` returned `fatal: not a git repository (or any of the parent directories): .git`.
- Repository path, baseline revision, working-tree changes, public interface inventory, concrete refactoring defects, runtime, dependency manager and validator commands: unknown. No implementation or validation has run.
- Actual capability gap: target project evidence is absent. Do not invent source, validator commands, remote facts or green checks. Use a supplied or otherwise evidence-supported repository; do not search unrelated private directories or substitute a synthetic project.
- Current host offers file/command tools and independent agents, with network enabled and no permission prompts. Recheck only if the environment changes. Goal/status, quota-reset and automatic same-goal wakeup capabilities have not been verified; promise no automatic resume. This file is the manual recovery entrypoint.
- No remote, branch, PR, account, deployment or destructive target is resolved or currently needed. Do not perform speculative remote operations.

## Authorization and safety

All user-authorizable actions necessary within the confirmed scope are pre-authorized, including file/dependency/environment changes, worktrees, Git operations, pushes, PRs, tests, review responses, Chrome uploads and entry of already available credentials when actually necessary. Do not ask again, wait, defer or mark blocked merely because an in-scope action ordinarily requires authorization. This does not expand scope, create credentials/sessions/tools, or override higher-priority host rules. Never expose, echo, screenshot, transcribe, persist, commit or publish credential values; keep credential-bearing UI out of evidence. Record only redacted outcomes.

Resolve any necessary remote/destructive target and impact from evidence before acting. Default to no push or PR unless required for the confirmed outcome. Unapproved API/schema/dependency changes stay outside scope; do all independent in-scope work before raising a genuinely blocking scope decision. For actual capability gaps, use safe alternatives, keep the affected completion gate open and continue independent work.

## Initialization TODO — execution prerequisites

1. Establish the real repository from user-provided or otherwise task-linked evidence. If it remains unavailable, record the missing-source dependency; ask only for information that cannot reasonably be inferred after independent preparation is exhausted.
2. Read the nearest applicable AGENTS.md, contributor rules, existing authoritative specifications and relevant CI/package scripts. Record their exact paths, the checkout revision and pre-existing user changes; preserve those changes.
3. Inspect cache implementation, public entrypoints/re-exports/types, callers and tests. Record exact public keys/signatures and any material ordering, error, timing, lifecycle or mutation behavior actually present. Do not infer compatibility boundaries solely from the directory name.
4. Identify concrete structural problems and a bounded refactoring plan. Record existing targeted validator commands and the smallest necessary broader checks exactly as defined by the repository. Establish the pre-change result and distinguish pre-existing failures from regressions.

After completing an initialization item, retain its verified result in the appropriate section and remove the completed TODO entry. Recheck initialization only when the baseline, scope, design or environment materially changes. Do not create separate todo/design/lessons files unless their documented triggers arise.

## Phases and conjunctive completion gates

All gates below are OPEN; generating this goal is not execution evidence.

1. **Baseline and contract:** repository and source paths verified; relevant policies followed; public API and behavioral baseline documented from implementation, callers and specifications; exact validators identified and baseline failures recorded.
2. **Bounded internal refactor:** concrete responsibilities/structure improved with a focused diff; public exports, entrypoints, signatures, types and observable behavior remain compatible; existing callers require no public API migration. Test affected paths after each frozen change batch. Keep unrelated modifications out of the diff.
3. **Behavior and validation:** add meaningful regression coverage for uncovered affected behavior and boundaries, using existing infrastructure. Run real cache-focused tests plus the smallest applicable integration/type/build or other repository-required gates. Record exact commands, exit results, failures and evidence tied to the current revision. Historical green runs and newly written requirements are not proof; preserve assertions, thresholds and exit semantics. Investigate failures across the affected call paths and fix root causes. Broaden or repeat validation only for changed integration seams, new failures or unresolved concerns.
4. **Documentation:** update directly affected documentation if structure or maintenance guidance changes; preserve public usage contracts. If no documentation change is warranted, record the evidence-based reason.
5. **Independent review:** use 3 independent read-only reviewers at major behavior-sensitive refactor milestones and again at final integration. Each inspects the integrated diff and validation evidence; implementers do not count. At final integration use distinct correctness/tests, API/design boundaries and security/maintainability emphases without limiting any reviewer's full-diff inspection. Findings include severity, exact location, observed evidence and recommendation. Fix findings and re-review affected changes; at most 3 fix/re-review rounds per item before deferring unresolved work without claiming completion. If reviewers are unavailable, keep this gate open, record recovery conditions and finish review-independent work; self-review cannot replace it.
6. **Final integration:** current combined diff satisfies all preceding gates, contains only request-related changes, and has no unresolved material findings or mandatory validation failures. Re-run affected checks after integration changes. Report completed results, verification and any remaining work honestly; completion requires every gate, not merely passing tests.

## Execution loop, waits and recovery

- Batch by cache responsibility, root cause or validation surface. Freeze a batch before its checks; broader checks run at phase boundaries or for a new concern.
- Try an item at most 3 times. Record failure evidence, recovery options, dependencies and the unblock condition. Then move the item and its dependents behind independent work, marking it waiting/deferred/needs-input without waiving its gate. Recheck when the unblock condition changes or at phase boundaries.
- During useful waits continue non-conflicting caller inventory, read-only test/failure analysis, acceptance preparation or necessary documentation/state updates. Do not invent busywork. Waiting, deferred and needs-input items always move behind meaningful independent work.
- After each productive loop report completed evidence, remaining gates and one next action. Do not report a percentage without a defined denominator or claim full completion before every gate passes.
- Before context compaction, handoff or a quota wait, save the latest revision, uncommitted changed paths, completed/remaining work, validation/review evidence, active waits, recovery conditions and exactly one next action. Resume by comparing this state with the actual checkout and evidence.
- A first failure, repairable test, review queue or quota wait does not itself justify stopping. Reduce concurrency/batch size or use verified safe alternatives when constrained. Never invent a quota reset time, accepted goal status, resume command or wakeup tool. Use native non-blocking recovery only when available; otherwise preserve this manual resume entrypoint.
- Overall blocked requires recovery, alternatives and meaningful independent work to be exhausted, all meaningful remaining work to share the same verified mandatory external dependency, safety boundary or logical conflict, and the current host's status/audit rules to be satisfied. Three retries in one turn alone do not satisfy any audit requiring the same blocker across consecutive goal turns. Handle an explicit user pause under host rules.

## Parallel ownership and commits

- Do not split tightly coupled cache implementation mechanically. If genuinely independent work is useful, specify each lane's inputs, output, exclusive file/responsibility ownership and dependencies first. Shared exports, lockfiles and generated metadata have one owner. Tell workers they are not alone and must not revert others' edits. The primary agent owns integration and reruns affected checks; a worker's green run is not integration evidence.
- Commit persistent milestones locally only after applicable validation and independent review pass. No empty commits and no push by default. A necessary intermediate checkpoint must state unmet gates explicitly and cannot claim they passed. Never weaken mandatory validators or drop high-severity findings to create a milestone.

## Current checkpoint and next action

- Completed: skill/context investigation, user confirmation, Deep-mode initialization and goal preparation.
- Unstarted: repository resolution, API inventory, refactoring, tests, documentation assessment and independent review.
- Latest project revision: unknown; no project files changed and no project commit created.
- Next action when the goal is explicitly started: establish the real target repository from task-linked evidence, then complete Initialization TODO before any implementation.
