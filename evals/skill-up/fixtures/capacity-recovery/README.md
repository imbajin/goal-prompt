# Native capacity recovery fixture

`test-native-host.py` runs real Codex 0.164.0 in a disposable Docker container
against a loopback scripted Responses provider. The container has no external
network, host bind, existing login or business thread. This tests injected
capacity and host state transitions, not online capacity or model quality.

Build the existing `scripts/baseline-container/` image and pass its immutable
image ID explicitly. That profile provides Python and `codex-upstream`.

```sh
python3 evals/skill-up/fixtures/capacity-recovery/test-native-host.py \
  --image YOUR_IMAGE_ID --output .eval-work/native-capacity-new
```

An optional `--recovery-script path/to/prototype.py` loads the prototype's
`run(options, rpc, ledger)` function through a serialized **real native stdio
RPC adapter**. The watcher runs in a controller thread outside the Codex host.
It is armed before releasing the injected error. This is not a CLI socket
end-to-end test. No WebSocket or daemon compatibility is implied.

With a recovery prototype, use `--scenario recovery`, `--scenario pause`, or
`--scenario quota`. The positive case checks the same generated Goal ID through
read-only access to the disposable fixture DB, preserves objective/budget,
waits for a new native turn, and then pauses that fixture Goal to prevent a
synthetic uncompleted objective from looping. The negatives verify that user
pause during backoff and non-capacity quota termination produce no recovery
write. The quota host state is `usageLimited`, distinct from `blocked`.

Every output path must be new. Config, native JSON-RPC events, image policy,
script hashes, generated rollouts and failures remain under the local ignored
output directory. Only containers created by this invocation are removed.

Cleanup is attempted even if Docker start or evidence collection fails. A Docker
removal failure can still require manual cleanup: use the output's
`container-id.txt` to identify only the container owned by that invocation.
`test-native-host-cleanup.py` checks start/collection failures without Docker
or model calls; it does not establish that Docker can remove a container during
an engine outage.

The recorded native observations refer to each run's archived fixture SHA.
After those runs, only failure-path cleanup was changed and checked by the
zero-Docker fault tests; the original native results were not overwritten or
presented as another run of the revised fixture.
