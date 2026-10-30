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

The command above is self-contained: it verifies host capacity/block/reactivate
transitions through the fixture client and needs no private prototype. To test
the experimental automatic policy, this repository also includes
`retry_policy.py`; it has no socket client, daemon, credentials or standalone
Desktop entrypoint and is not installed with the Skill.

```sh
python3 evals/skill-up/fixtures/capacity-recovery/test-native-host.py \
  --image YOUR_IMAGE_ID --output .eval-work/native-policy-new \
  --recovery-script evals/skill-up/fixtures/capacity-recovery/retry_policy.py \
  --scenario recovery
```

Use a new output directory with `--scenario pause` or `--scenario quota` for the
negative controls. `--recovery-script` imports `run(options, rpc, ledger)` through
a serialized **real native stdio RPC adapter**. The watcher is a controller
thread outside the Codex host and is armed before the injected terminal error.
This is not a CLI socket end-to-end test or online capacity test.

The positive checks the same native Goal ID through read-only access to the
disposable fixture DB, preserves objective/budget, waits for a new native turn,
then pauses that fixture Goal to prevent an uncompleted synthetic objective from
looping. The negatives verify pause and quota produce no recovery write;
quota state is `usageLimited`, distinct from `blocked`.

The policy's test defaults are 5/15/30 minutes, at most three attempts, with no
jitter unless configured. Jitter is capped with the backoff; a longer explicit
retry hint remains a minimum wait and is never shortened by that cap.
A new failed turn is not recovery: immediate repeated capacity failures consume
the remaining backoff attempts even if polling never sampled them in progress.
Recovery requires an in-progress or completed new turn and a non-blocked,
non-paused Goal. Native tests use a scaled 0.25-second wait. Run the
virtual-clock and cleanup tests without Docker or model credentials:

```sh
python3 evals/skill-up/fixtures/capacity-recovery/test_retry_policy.py
python3 evals/skill-up/fixtures/capacity-recovery/test-native-host-cleanup.py
```

One policy test deliberately demonstrates the remaining final GET-to-SET race.
It is a known limitation, not a safety pass. Do not use the laboratory module as
a Desktop recovery service; atomic conditions and supported connection/lifecycle
handling are still required before that capability can be released.

Every output path must be new. Config, native JSON-RPC events, image policy,
script hashes, generated rollouts and failures remain under the local ignored
output directory. Only containers created by this invocation are removed.

Cleanup is attempted even if Docker start or evidence collection fails. A Docker
removal failure can still require manual cleanup: use the output's
`container-id.txt` to identify only the container owned by that invocation.
`test-native-host-cleanup.py` checks start/collection failures without Docker
or model calls; it does not establish that Docker can remove a container during
an engine outage.

The recorded native observations refer to each run's archived fixture and policy
SHA. Earlier native runs and the cleanup-only revision remain archived. The R1
follow-up reran the three scenarios with the repository policy module; it did
not overwrite earlier results or run an online provider.
