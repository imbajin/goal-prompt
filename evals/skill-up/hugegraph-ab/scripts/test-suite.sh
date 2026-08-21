#!/usr/bin/env bash
set -euo pipefail

scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
suite_dir="$(cd "$scripts_dir/.." && pwd)"
repo_root="$(cd "$suite_dir/../../.." && pwd)"
test_root="$repo_root/.eval-work/hugegraph-ab/self-test-$$"
mkdir -p "$test_root/source" "$test_root/evidence"
printf '<project><version>fake</version></project>\n' >"$test_root/source/pom.xml"
printf '# Safe version evidence\n\n- 1.5.0\n- 1.7.0\n- master development line\n' >"$test_root/evidence/version-evidence.md"

for case_id in \
  toolchain-empty-graph-edit \
  server-hstore-graph-isolation \
  docs-graphs-api-version-truth
do
  pair_root="$test_root/pairs/$case_id/fake-01"
  "$scripts_dir/prepare-fixtures.sh" \
    --case "$case_id" \
    --pair-id fake-01 \
    --source "$test_root/source" \
    --evidence "$test_root/evidence" \
    --allow-unprobed \
    --output-root "$test_root"
  "$scripts_dir/run-prompt-pairs.sh" \
    --paired \
    --pair-root "$pair_root" \
    --fake-generator "$suite_dir/fixtures/fakes/fake-generator.sh"
  HG_AB_SECRET_SENTINEL=must-not-leak "$scripts_dir/run-execution-pairs.sh" \
    --pair-root "$pair_root" \
    --executor "$suite_dir/fixtures/fakes/fake-executor.sh" \
    --isolation-wrapper "$suite_dir/fixtures/fakes/fake-network-wrapper.sh" \
    --oracle "$suite_dir/fixtures/fakes/fake-oracle.sh" \
    --fake
done

sealed_cases=(toolchain-empty-graph-edit server-hstore-graph-isolation docs-graphs-api-version-truth)
for case_index in 0 1 2; do
  case_id="${sealed_cases[$case_index]}"
  metadata="$test_root/sealed-metadata-$case_id.json"
  python3 -c '
import importlib.util, json, pathlib, sys
spec=importlib.util.spec_from_file_location("suite", sys.argv[1]); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
value={"case_id":sys.argv[2],"status":"active","refresh_mode":"online","version_drift":False,"source_sha256":module.tree_digest(pathlib.Path(sys.argv[3])),"version_evidence_sha256":module.tree_digest(pathlib.Path(sys.argv[4]))}
pathlib.Path(sys.argv[5]).write_text(json.dumps(value)+"\n")
' "$scripts_dir/suite.py" "$case_id" "$test_root/source" "$test_root/evidence" "$metadata"
  if ((case_index == 1)); then order=ba; else order=ab; fi
  "$scripts_dir/prepare-fixtures.sh" \
    --case "$case_id" --pair-id pilot-01 --cohort pilot --cohort-id sealed-pilot --repeat 1 \
    --prompt-order "$order" --execution-order "$order" \
    --source "$test_root/source" --evidence "$test_root/evidence" \
    --preflight-metadata "$metadata" --output-root "$test_root/sealed-root" >/dev/null
done

first_pair="$test_root/pairs/toolchain-empty-graph-edit/fake-01"
if [[ -n "${HG_AB_SKILL_UP:-}" ]]; then
  "$scripts_dir/run-prompt-pairs.sh" \
    --skill-up "$HG_AB_SKILL_UP" \
    --paired --dry-run \
    --pair-root "$first_pair" \
    --runtime opensandbox \
    --sandbox-template hugegraph-ab-dry-run \
    --opensandbox-base-url https://opensandbox.example.invalid \
    --model fake-dry-run \
    --model-base-url https://model-proxy.example.invalid/v1 \
    --model-egress-target model-proxy.example.invalid \
    --model-policy-url https://model-proxy.example.invalid/policy \
    --model-policy-identity dry-run-provider-only \
    --reasoning-effort medium >/dev/null
  # A dry-run must not leave a read-only runtime tree that blocks the next
  # materialization for the same pair.
  "$scripts_dir/run-prompt-pairs.sh" \
    --skill-up "$HG_AB_SKILL_UP" \
    --paired --dry-run \
    --pair-root "$first_pair" \
    --runtime opensandbox \
    --sandbox-template hugegraph-ab-dry-run \
    --opensandbox-base-url https://opensandbox.example.invalid \
    --model fake-dry-run \
    --model-base-url https://model-proxy.example.invalid/v1 \
    --model-egress-target model-proxy.example.invalid \
    --model-policy-url https://model-proxy.example.invalid/policy \
    --model-policy-identity dry-run-provider-only \
    --reasoning-effort medium >/dev/null
fi
if "$scripts_dir/run-prompt-pairs.sh" --dry-run >/dev/null 2>&1; then
  echo "prompt runner accepted dry-run without explicit --paired" >&2
  exit 1
fi
if "$scripts_dir/run-prompt-pairs.sh" --paired --pair-root "$first_pair" >/dev/null 2>&1; then
  echo "prompt runner accepted execution without fake generator or --run-models" >&2
  exit 1
fi
if "$suite_dir/fixtures/fakes/fake-network-wrapper.sh" true >/dev/null 2>&1; then
  echo "fake network wrapper accepted a non-fake run" >&2
  exit 1
fi

"$scripts_dir/prepare-fixtures.sh" \
  --case toolchain-empty-graph-edit \
  --pair-id failure-01 \
  --source "$test_root/source" \
  --evidence "$test_root/evidence" \
  --allow-unprobed \
  --output-root "$test_root/failure-root" >/dev/null
failure_pair="$test_root/failure-root/pairs/toolchain-empty-graph-edit/failure-01"
"$scripts_dir/run-prompt-pairs.sh" \
  --paired \
  --pair-root "$failure_pair" \
  --fake-generator "$suite_dir/fixtures/fakes/fake-generator.sh"
if "$scripts_dir/run-execution-pairs.sh" \
  --pair-root "$failure_pair" \
  --executor "$suite_dir/fixtures/fakes/fake-model-failure-executor.sh" \
  --isolation-wrapper "$suite_dir/fixtures/fakes/fake-network-wrapper.sh" \
  --oracle "$suite_dir/fixtures/fakes/fake-oracle.sh" \
  --fake >/dev/null 2>&1
then
  echo "execution runner hid deliberate executor failures" >&2
  exit 1
fi
python3 "$scripts_dir/summarize-pairs.py" \
  --cohort deterministic \
  --pair-root "$failure_pair" \
  --anonymous-diagnostics \
  --output "$test_root/failure-summary.json" >/dev/null

"$scripts_dir/prepare-fixtures.sh" \
  --case toolchain-empty-graph-edit \
  --pair-id env-failure-01 \
  --source "$test_root/source" \
  --evidence "$test_root/evidence" \
  --allow-unprobed \
  --output-root "$test_root/env-root" >/dev/null
env_pair="$test_root/env-root/pairs/toolchain-empty-graph-edit/env-failure-01"
"$scripts_dir/run-prompt-pairs.sh" \
  --paired --pair-root "$env_pair" \
  --fake-generator "$suite_dir/fixtures/fakes/fake-generator.sh"
if "$scripts_dir/run-execution-pairs.sh" \
  --pair-root "$env_pair" \
  --executor /usr/bin/false \
  --isolation-wrapper "$suite_dir/fixtures/fakes/fake-network-wrapper.sh" \
  --oracle "$suite_dir/fixtures/fakes/fake-oracle.sh" \
  --fake >/dev/null 2>&1
then
  echo "execution runner hid deliberate environment failures" >&2
  exit 1
fi
python3 "$scripts_dir/summarize-pairs.py" \
  --cohort deterministic --pair-root "$env_pair" --anonymous-diagnostics \
  --output "$test_root/env-summary.json" >/dev/null

"$scripts_dir/prepare-fixtures.sh" \
  --case toolchain-empty-graph-edit \
  --pair-id partial-01 \
  --source "$test_root/source" \
  --evidence "$test_root/evidence" \
  --allow-unprobed \
  --output-root "$test_root/partial-root" >/dev/null
partial_pair="$test_root/partial-root/pairs/toolchain-empty-graph-edit/partial-01"
"$scripts_dir/run-prompt-pairs.sh" \
  --paired --pair-root "$partial_pair" \
  --fake-generator "$suite_dir/fixtures/fakes/fake-generator.sh"
python3 -c '
import json, pathlib, sys
pair = pathlib.Path(sys.argv[1])
mapping = json.loads((pair / "private/mapping.json").read_text())
arm = mapping["roles"]["without_skill"]
path = pair / "arms" / arm / "prompt/metrics.json"
value = json.loads(path.read_text())
value.update({"status": "ERROR", "failure_kind": "prompt_runtime_error", "failure_class": "environment", "cli_exit_code": 1})
path.write_text(json.dumps(value, indent=2) + "\n")
' "$partial_pair"
if "$scripts_dir/run-execution-pairs.sh" \
  --pair-root "$partial_pair" \
  --executor "$suite_dir/fixtures/fakes/fake-executor.sh" \
  --isolation-wrapper "$suite_dir/fixtures/fakes/fake-network-wrapper.sh" \
  --oracle "$suite_dir/fixtures/fakes/fake-oracle.sh" \
  --fake >/dev/null 2>&1
then
  echo "execution runner accepted a partial Prompt ERROR as executable" >&2
  exit 1
fi

"$scripts_dir/prepare-fixtures.sh" \
  --case toolchain-empty-graph-edit \
  --pair-id quality-fail-01 \
  --source "$test_root/source" \
  --evidence "$test_root/evidence" \
  --allow-unprobed \
  --output-root "$test_root/quality-root" >/dev/null
quality_pair="$test_root/quality-root/pairs/toolchain-empty-graph-edit/quality-fail-01"
"$scripts_dir/run-prompt-pairs.sh" \
  --paired --pair-root "$quality_pair" \
  --fake-generator "$suite_dir/fixtures/fakes/fake-generator.sh"
python3 -c '
import json, pathlib, sys
pair = pathlib.Path(sys.argv[1])
mapping = json.loads((pair / "private/mapping.json").read_text())
arm = mapping["roles"]["without_skill"]
path = pair / "arms" / arm / "prompt/metrics.json"
value = json.loads(path.read_text())
value.update({"status": "FAIL", "failure_kind": None, "cli_exit_code": 1})
path.write_text(json.dumps(value, indent=2) + "\n")
' "$quality_pair"
"$scripts_dir/run-execution-pairs.sh" \
  --pair-root "$quality_pair" \
  --executor "$suite_dir/fixtures/fakes/fake-executor.sh" \
  --isolation-wrapper "$suite_dir/fixtures/fakes/fake-network-wrapper.sh" \
  --oracle "$suite_dir/fixtures/fakes/fake-oracle.sh" \
  --fake

python3 "$scripts_dir/summarize-pairs.py" \
  --cohort deterministic \
  --pair-root "$test_root/pairs/toolchain-empty-graph-edit/fake-01" \
  --pair-root "$test_root/pairs/server-hstore-graph-isolation/fake-01" \
  --pair-root "$test_root/pairs/docs-graphs-api-version-truth/fake-01" \
  --output "$test_root/summary.json"

make_repo() {
  local path="$1"
  local remote="$2"
  mkdir -p "$path"
  git -C "$path" init -q
  git -C "$path" config user.name hugegraph-ab
  git -C "$path" config user.email hugegraph-ab@example.invalid
  git -C "$path" remote add origin "$remote"
  printf '<project><properties><revision>1.8.0</revision><hugegraph.version>1.7.0</hugegraph.version></properties></project>\n' >"$path/pom.xml"
  mkdir -p \
    "$path/hugegraph-hubble/hubble-fe/src/modules/analysis/QueryResult/Home" \
    "$path/hugegraph-hubble/hubble-fe/src/modules/analysis/QueryResult/GraphResult/GraphMenubar" \
    "$path/hugegraph-hubble/hubble-fe/src/modules/component/EditElement"
  printf 'const graphData = { vertices: [], edges: [] };\n' \
    >"$path/hugegraph-hubble/hubble-fe/src/modules/analysis/QueryResult/Home/index.js"
  printf 'const New = { vertex: true, edge: false, disabled: false };\n' \
    >"$path/hugegraph-hubble/hubble-fe/src/modules/analysis/QueryResult/GraphResult/GraphMenubar/index.js"
  printf 'const properties = schema.nullable || [];\n' \
    >"$path/hugegraph-hubble/hubble-fe/src/modules/component/EditElement/index.js"
  git -C "$path" add .
  git -C "$path" commit -qm initial
  git -C "$path" branch -M master
  git -C "$path" tag 1.5.0
  git -C "$path" tag 1.7.0
}

make_repo "$test_root/toolchain-repo" https://github.com/apache/hugegraph-toolchain.git
printf '#!/usr/bin/env bash\nexit 0\n' >"$test_root/active-probe"
printf '#!/usr/bin/env bash\nexit 10\n' >"$test_root/stale-probe"
chmod +x "$test_root/active-probe" "$test_root/stale-probe"
"$scripts_dir/preflight.sh" \
  --case toolchain-empty-graph-edit \
  --repo "$test_root/toolchain-repo" \
  --output "$test_root/preflight-active" \
  --offline \
  --stale-probe "$test_root/active-probe"
"$scripts_dir/preflight.sh" \
  --case toolchain-empty-graph-edit \
  --repo "$test_root/toolchain-repo" \
  --output "$test_root/preflight-stale" \
  --offline \
  --stale-probe "$test_root/stale-probe"

"$scripts_dir/prepare-fixtures.sh" \
  --case toolchain-empty-graph-edit \
  --pair-id bound-preflight \
  --cohort deterministic \
  --source "$test_root/preflight-active/source" \
  --evidence "$test_root/preflight-active/version-evidence" \
  --preflight-metadata "$test_root/preflight-active/metadata.json" \
  --output-root "$test_root/bound-root" >/dev/null
if "$scripts_dir/prepare-fixtures.sh" \
  --case toolchain-empty-graph-edit \
  --pair-id mismatched-preflight \
  --cohort deterministic \
  --source "$test_root/preflight-active/source" \
  --evidence "$test_root/evidence" \
  --preflight-metadata "$test_root/preflight-active/metadata.json" \
  --output-root "$test_root/mismatch-root" >/dev/null 2>&1
then
  echo "fixture preparation accepted mismatched preflight evidence" >&2
  exit 1
fi

git -C "$test_root/toolchain-repo" tag 1.8.0
"$scripts_dir/preflight.sh" \
  --case toolchain-empty-graph-edit \
  --repo "$test_root/toolchain-repo" \
  --output "$test_root/preflight-drift" \
  --offline \
  --stale-probe "$test_root/active-probe"

make_docs_repo() {
  local path="$1"
  mkdir -p "$path/content/en/docs/clients/restful-api" "$path/content/cn/docs/clients/restful-api"
  git -C "$path" init -q
  git -C "$path" config user.name hugegraph-ab
  git -C "$path" config user.email hugegraph-ab@example.invalid
  git -C "$path" remote add origin https://github.com/apache/hugegraph-doc.git
  printf 'graphspace graphs Content-Type text/plain application/json backend auth status\n' >"$path/content/en/docs/clients/restful-api/graphs.md"
  printf 'graphspace graphs Content-Type text/plain application/json backend 鉴权 状态\n' >"$path/content/cn/docs/clients/restful-api/graphs.md"
  git -C "$path" add .
  git -C "$path" commit -qm initial
  git -C "$path" branch -M master
  git -C "$path" branch release-1.5.0
  git -C "$path" tag 1.7.0
}

make_server_repo() {
  local path="$1"
  mkdir -p \
    "$path/hugegraph-server/hugegraph-api/src/main/java/org/apache/hugegraph/api" \
    "$path/hugegraph-server/hugegraph-api/src/main/java/org/apache/hugegraph/auth" \
    "$path/hugegraph-server/hugegraph-core/src/main/java/org/apache/hugegraph/backend/store"
  git -C "$path" init -q
  git -C "$path" config user.name hugegraph-ab
  git -C "$path" config user.email hugegraph-ab@example.invalid
  git -C "$path" remote add origin https://github.com/apache/hugegraph.git
  printf '<project><version>1.7.0</version></project>\n' >"$path/pom.xml"
  printf '@Path("graphspaces/{graphspace}/graphs") @POST @GET @DELETE creator username()\n' \
    >"$path/hugegraph-server/hugegraph-api/src/main/java/org/apache/hugegraph/api/GraphsAPI.java"
  printf 'String username() { return getContext() == null ? "anonymous" : getContext().user().username(); }\n' \
    >"$path/hugegraph-server/hugegraph-api/src/main/java/org/apache/hugegraph/auth/HugeGraphAuthProxy.java"
  printf 'void createGraph(String graphspace, String creator) {}\n' \
    >"$path/hugegraph-server/hugegraph-api/src/main/java/org/apache/hugegraph/auth/GraphManager.java"
  printf 'static final Set<String> ALLOWED_BACKENDS = Set.of("hstore");\n' \
    >"$path/hugegraph-server/hugegraph-core/src/main/java/org/apache/hugegraph/backend/store/BackendProviderFactory.java"
  git -C "$path" add .
  git -C "$path" commit -qm initial
  git -C "$path" branch -M master
  git -C "$path" tag 1.5.0
  git -C "$path" tag 1.7.0
}

make_docs_repo "$test_root/docs-repo"
make_server_repo "$test_root/server-repo"
"$scripts_dir/preflight.sh" \
  --case docs-graphs-api-version-truth \
  --repo "$test_root/docs-repo" \
  --server-repo "$test_root/server-repo" \
  --output "$test_root/preflight-docs" \
  --offline \
  --stale-probe "$test_root/active-probe"

python3 "$scripts_dir/test-suite.py" --root "$test_root"
