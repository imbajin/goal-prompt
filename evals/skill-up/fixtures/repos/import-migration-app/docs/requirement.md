# Import migration requirement

## Outcome

All valid records are imported exactly once, and rejected records receive a stable reason code.

## Scope

- Batch import implementation and tests.
- Recovery after an interrupted batch.
- Compatibility with the current input schema.

## Acceptance

- Unit, integration, and type checks pass.
- Replaying a completed batch creates no duplicates.
