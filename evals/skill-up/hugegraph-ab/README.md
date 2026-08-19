# HugeGraph two-stage paired A/B suite

This suite compares three byte-identical Raw Requests with and without
`goal-prompt`, then forwards each generated response verbatim to the same
downstream executor in a fresh HugeGraph fixture. It is separate from
`evals/skill-up/eval.yaml`, disabled by default, and does not run models unless
the operator supplies explicit real-run flags.

## Safety and causal contract

- `cases/*.yaml` is byte-checked against the Raw Requests in
  `docs/hugegraph-ab-test-prompts.zh-CN.md`.
- A prompt pair is two independent single-role skill-up runs. The control
  runtime root contains no Skill files; the treatment root contains the local
  `goal-prompt` tree. Their runtime,
  model, reasoning effort, timeout, maximum turns, source, and evidence are
  identical; only `skills: []` versus the local `goal-prompt` skill differs.
  `--order ab|ba` controls which role runs first.
- Prompt and execution failures are retained for both anonymous arms. Automatic
  retries are zero; prepare a new balanced pair instead of selectively
  rerunning one arm.
- Preflight resolves a moving ref once per pair. `prepare` verifies that source,
  version evidence, metadata, and runtime tree digests belong to the same
  preflight, then creates isolated workspace/HOME/session/data trees.
- Real downstream execution only accepts `scripts/container-isolation.sh`.
  A reviewed service spec creates a fresh network and data root for each
  anonymous arm. The executor gets one arm's paths, a private Docker volume,
  a read-only version-evidence mount, and only an Agent-writable artifact
  directory. It cannot mount trusted scores, the pair mapping, sibling arm,
  pristine source, repository, judge, or oracle. A real HTTP/TCP probe checks
  private-service health, provider-only policy, public denial, and CONNECT
  rejection before the Agent runs.
- The reviewed oracle command spec runs under a root controller in a second
  disposable container with a clean environment. Probe commands run as an
  unprivileged UID against disposable workspace/pristine volumes; root-only
  spec/runner files and the root-owned evidence path are not readable or
  writable by those commands. Evidence is copied out after the container exits;
  untrusted Maven/Node/Hugo code never runs on the host or sees trusted scores.
- Critical failures produce an effective score of zero and are reported
  separately from ordinary wins/losses. Prompt/executor model failures receive
  a trusted zero score; environment failures remain unscored. A real summary
  requires the exact preregistered cohort ledger and does not read the private
  role mapping until every anonymous arm has a bound trusted score. Each score
  binds the retained behavior-evidence bytes; the cohort identity also fixes
  the judge, oracle adapter, network probe, and container resource limits.
- Runtime hashes/IDs, model text, results, and mappings live only under ignored
  `.eval-work/`. No golden model output, persistent history baseline, frozen
  prose contract, threshold, or CI/merge enforcement is added.

## Layout

```text
evals/skill-up/hugegraph-ab/
├── eval.yaml
├── cases/                 # checked Raw Requests; benchmark disabled
├── rubrics/               # observable behavior scoring
├── oracles/               # deterministic adapters; real specs run isolated
├── scripts/               # preflight, pairing, isolation, judge, summary
└── fixtures/fakes/        # deterministic orchestration smoke only
```

## Deterministic validation (no model calls)

```bash
skill_up=.eval-work/tools/skill-up-bin/skill-up

"$skill_up" validate evals/skill-up/hugegraph-ab/eval.yaml
evals/skill-up/hugegraph-ab/scripts/run-prompt-pairs.sh \
  --skill-up "$skill_up" --paired --dry-run
HG_AB_SKILL_UP="$skill_up" \
  evals/skill-up/hugegraph-ab/scripts/test-suite.sh
```

The dry-run validates the checked config and lists exactly three cases; it does
not invoke an Agent. A pair-specific dry-run additionally requires explicit
`--pair-root`, `--runtime opensandbox`, `--sandbox-template`,
`--opensandbox-base-url`, `--model`, and
`--reasoning-effort`, plus the model base/policy identity, and validates both
ephemeral single-role configs.

The fake smoke proves orchestration, Raw Request identity, source/evidence
binding, anonymous mapping, verbatim transfer, failure retention, judge caps,
critical-score handling, stale/drift classification, and summary recomputation.
Its fake attestation is not evidence that host processes are isolated. The real
Docker wrapper must be separately exercised before a Pilot.

## Preflight and fixture preparation

Canonical repositories and trusted probes stay outside agent workspaces:

```bash
suite=evals/skill-up/hugegraph-ab
run=.eval-work/hugegraph-ab/preflight/toolchain

"$suite/scripts/preflight.sh" \
  --case toolchain-empty-graph-edit \
  --repo .eval-work/upstream/hugegraph-toolchain \
  --output "$run" \
  --stale-probe /absolute/path/to/trusted-toolchain-probe

"$suite/scripts/prepare-fixtures.sh" \
  --case toolchain-empty-graph-edit \
  --pair-id pilot-01 --cohort pilot --cohort-id pilot-20260820 --repeat 1 \
  --prompt-order ab --execution-order ba \
  --source "$run/source" \
  --evidence "$run/version-evidence" \
  --preflight-metadata "$run/metadata.json" \
  --output-root .eval-work/hugegraph-ab
```

Prepare every Pilot/Formal pair before running any arm. The final expected pair
automatically validates the complete 2/1 Prompt and execution schedule and
seals the cohort ledger; real Prompt/execution refuses an unsealed ledger or an
order that differs from the plan. Pair IDs may repeat across cases because the
ledger identity is `(case_id, pair_id)`.

The stale probe receives the exported source: `0` means active, `10` stale,
and any other exit is an environment failure. A missing probe is
`needs_probe`. `pilot` and `formal` require active online preflight; offline or
unprobed fixtures are allowed only for the deterministic cohort. Preflight
fails closed on unexpected official 1.8 refs or expected master POM drift and
includes scoped public API/source evidence, not issue/PR/root-cause answers.
The docs case also requires `--server-repo` for matching Server evidence.

## Real Prompt pair

The OpenSandbox runtime must be reviewed before use. It uses
`network_policy: allow_declared` for only the credential-free model endpoint.
Its setup probe reads that endpoint's policy document, rejects direct public
answer-source access and rejects a CONNECT tunnel. The host-only attestation
binds the template, model, reasoning effort, base/policy URLs and policy
identity, resolved sandbox image, authenticated control-plane channel, and a
non-secret auth identity. The API secret itself is never written to artifacts.

```bash
export HG_AB_OPENSANDBOX_API_KEY=<private-opensandbox-token>
export HG_AB_PROMPT_MODEL_API_KEY=<private-provider-token>

"$suite/scripts/run-prompt-pairs.sh" \
  --skill-up "$skill_up" --paired --run-models \
  --pair-root .eval-work/hugegraph-ab/pairs/toolchain-empty-graph-edit/pilot-01 \
  --runtime opensandbox --sandbox-template <reviewed-template> \
  --opensandbox-base-url https://<opensandbox-control-plane> \
  --runtime-attestation .eval-work/hugegraph-ab/runtime/prompt-attestation.json \
  --model <fixed-model> --model-base-url https://<provider-endpoint>/v1 \
  --model-egress-target <provider-endpoint> \
  --model-policy-url https://<provider-endpoint>/policy \
  --model-policy-identity <reviewed-policy-id> \
  --reasoning-effort <fixed-effort> \
  --timeout-seconds 900 --max-turns 18 --order ab
```

The provider token reaches each single-role runtime through a mode-`0600`
named pipe and is never persisted in the generated eval config or artifacts.

Each role is attempted even if its peer fails. A nonempty skill-up `FAIL`
response is still forwarded verbatim downstream. skill-up `ERROR`, timeout, or
missing runtime result is an unscored environment failure; a non-ERROR empty
model response is a trusted model-failure zero.

## Real downstream execution and trusted oracle

```text
executor <generated-goal-file> <writable-workspace> <artifact-dir>
service harness prepare|cleanup --spec ... --run-id ... --data-dir ...
oracle isolation CASE SPEC WORKSPACE PRISTINE AGENT_ARTIFACTS EXECUTOR_STDOUT TRUSTED_EVIDENCE
```

The reviewed executor contract uses exit `0` for a completed run and exit `10`
only for a confirmed model/task failure. Any other nonzero exit, including
container/copy/runtime failures, is conservatively retained as an unscored
environment error; it cannot enter A/B means or unlock unblinding.
Executor and oracle containers default to `1024` PIDs, `12g` memory, and `8`
CPUs; an operator override is recorded and must remain identical across the
cohort.

The reviewed service spec has `prepare_argv`, `cleanup_argv`, a stable
`service_config_identity`, no shell string, and an idempotent `cleanup_argv`
that is safe even when `prepare` only partially completed. `prepare` creates a unique
Docker `--internal` network and exclusive data root for the anonymous arm, then
writes an attestation containing its network, private health URLs, resolved
service image IDs, model base URL, model policy URL/identity, and freshness claims. The suite validates the
run ID/data root and refuses network reuse; the container probe verifies the
network claims before execution. Cleanup runs after every terminal path.

The host-owned, container-mounted oracle spec defines each `checks`, `facts`, and
`claims.complete` entry as an `argv` array plus an optional timeout. The claim
probe independently checks whether the Agent's final artifact says the task is
complete; it is not derived from behavior checks. Exit `0` means true, `1`
false; any other exit or timeout is an environment error. Placeholders are
`{workspace}`, `{pristine}`, `{agent_artifacts}`, `{executor_stdout}`, and
`{output}`.

```bash
export HG_AB_MODEL_API_KEY=<private-provider-token>

"$suite/scripts/run-execution-pairs.sh" \
  --pair-root .eval-work/hugegraph-ab/pairs/toolchain-empty-graph-edit/pilot-01 \
  --executor /absolute/path/to/the-same-executor \
  --isolation-wrapper "$suite/scripts/container-isolation.sh" \
  --executor-image <reviewed-local-executor-image> \
  --oracle-image <reviewed-local-oracle-image> \
  --service-harness "$suite/scripts/service-harness.py" \
  --service-spec /absolute/path/to/reviewed-toolchain-services.json \
  --oracle-isolation "$suite/scripts/oracle-isolation.sh" \
  --oracle-spec /absolute/path/to/reviewed-toolchain-oracle.json \
  --model <fixed-model> --reasoning-effort <fixed-effort> \
  --timeout-seconds 7200 --oracle-timeout-seconds 7200 \
  --max-turns 60 --max-retries 0 --order ba --run-executors
```

For Server, the file passed through `--oracle-spec` must independently bind
`rest_namespace` to an auth-enabled HugeGraph 1.7 HStore direct REST smoke and
bind PUT/MERGE/doGet/truncate/rollback/concurrency checks to real store-core
commands. Store-core alone cannot claim the full #3095 namespace behavior.

## Blinded diagnostics and cohort summary

If any arm lacks `score.json`, inspect only anonymous status; this path never
reads the private role mapping:

```bash
python3 "$suite/scripts/summarize-pairs.py" \
  --cohort pilot \
  --cohort-id pilot-20260820 \
  --ledger .eval-work/hugegraph-ab/cohorts/pilot-20260820/ledger.json \
  --pair-root .eval-work/hugegraph-ab/pairs/toolchain-empty-graph-edit/pilot-01 \
  --anonymous-diagnostics \
  --output .eval-work/hugegraph-ab/pilot-diagnostics.json
```

A normal Pilot summary requires exactly one scored pair for all three cases; a
Formal summary requires exactly three for each case and balanced first-role
counts (2/1) independently for Prompt and execution. Each pair records its own
source/evidence snapshot because moving refs are resolved once per pair; the
oracle/service policy remains fixed within a case. Pass every pair explicitly
so fake, stale, Pilot, Formal, or unrelated artifacts cannot be globbed in:

```bash
python3 "$suite/scripts/summarize-pairs.py" \
  --cohort pilot \
  --cohort-id pilot-20260820 \
  --ledger .eval-work/hugegraph-ab/cohorts/pilot-20260820/ledger.json \
  --pair-root <toolchain-pair> \
  --pair-root <server-pair> \
  --pair-root <docs-pair> \
  --output .eval-work/hugegraph-ab/pilot-summary.json
```

The report separates ordinary and critical outcomes, completion and critical
rates, Prompt and execution metrics, and per-pair deltas. A role's weighted
score is suppressed if any run has a critical failure. Three repeats are an
engineering exploration, not statistical significance or proof that Treatment
is better.
