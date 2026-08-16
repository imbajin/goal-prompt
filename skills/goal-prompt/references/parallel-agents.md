# Parallel-Agent Task Splitting

Use this guidance only when the work contains genuinely independent lanes. Do
not split a focused task merely to appear parallel.

## Before splitting

- State the single outcome, shared invariants, acceptance gates, and integration
  owner in `state.md` or the confirmed task brief.
- Split by subsystem, page, root cause, or validation surface with a clear input
  and output. Do not split a single file or a shared mutable interface between
  multiple writers.
- Assign exclusive file and responsibility ownership. Name shared write points
  such as lockfiles, schemas, generated files, and release metadata and give
  each one a single owner.
- Keep the dependency graph explicit: a lane may start only after its stated
  inputs and baseline are available.

## During parallel work

- Every worker records its own changed paths, commands, evidence, assumptions,
  and unresolved risks. Workers are not alone in the repository and must not
  revert or overwrite another lane's changes.
- The integration owner resolves seams, reruns affected checks after combining
  lanes, and owns the final diff. A worker's local green test is not integration
  evidence.
- Do not let parallel waits create busywork. Continue only non-conflicting,
  useful work while another lane waits on CI, downloads, or an external service.
- Do not ask one worker to both create and delete the same artifact when a
  separate cleanup or review lane is needed.

## Review and merge

- Independent reviewers are not implementers. Parallel implementation does not
  reduce the required reviewer count or replace re-review after a fix.
- Reviewers inspect the integrated diff and its evidence, not just a worker's
  branch. Re-run checks at each seam that can change behavior.
- Queue integration when lanes overlap or the baseline changes; do not silently
  rebase, rewrite CI, or push while another lane is working.
- If one lane fails, record it and continue independent lanes. Do not claim the
  overall goal complete until every lane and integration gate passes.
