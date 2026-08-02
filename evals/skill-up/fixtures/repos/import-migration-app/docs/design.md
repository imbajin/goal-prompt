# Import migration design

- Preserve `importBatch(records)`.
- Use batch IDs as idempotency keys.
- Persist the last completed checkpoint before acknowledging a batch.
- Keep reason codes stable for existing rejected inputs.
