# Repository instructions

- Authentication changes are limited to `src/auth/middleware.ts` and its tests.
- Preserve the exported `authenticate(request)` contract.
- Do not add dependencies.
- Required validation: `npm run test:auth` and `npm run typecheck`.
