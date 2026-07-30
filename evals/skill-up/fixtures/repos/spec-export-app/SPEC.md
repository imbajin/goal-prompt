# Export manifest plan

## Outcome

Exporting a project produces `dist/manifest.json` with deterministic ordering.

## Scope

- Add manifest generation in `src/export.js`.
- Preserve the exported `exportProject(project)` API.
- Cover empty and multi-file projects.

## Exclusions

- No archive format changes.
- No new dependencies.

## Acceptance

- Existing export behavior remains compatible.
- Manifest paths are sorted lexicographically.
- `npm run test:export` and `npm run typecheck` pass.
