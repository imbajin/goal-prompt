#!/usr/bin/env bash
set -euo pipefail

if (($# != 7)); then
  echo "usage: oracle-isolation.sh CASE SPEC WORKSPACE PRISTINE AGENT_ARTIFACTS EXECUTOR_STDOUT OUTPUT" >&2
  exit 2
fi

case_id="$1"
spec="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
workspace="$(cd "$3" && pwd)"
pristine="$(cd "$4" && pwd)"
agent_artifacts="$(cd "$5" && pwd)"
executor_stdout="$(cd "$(dirname "$6")" && pwd)/$(basename "$6")"
output="$(cd "$(dirname "$7")" && pwd)/$(basename "$7")"
scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
image="${HG_AB_ORACLE_IMAGE:-}"
network="${HG_AB_PRIVATE_NETWORK:-}"
run_id="${AB_RUN_ID:-}"
expected_source_sha256="${HG_AB_SOURCE_SHA256:-}"
expected_runtime_bundle_sha256="${HG_AB_RUNTIME_BUNDLE_SHA256:-}"

[[ -n "$image" && -n "$network" && -n "$run_id" && -n "$expected_source_sha256" && -n "$expected_runtime_bundle_sha256" ]] || {
  echo "HG_AB_ORACLE_IMAGE, HG_AB_PRIVATE_NETWORK, AB_RUN_ID, and HG_AB_SOURCE_SHA256 are required" >&2
  exit 1
}
[[ -f "$spec" && -d "$workspace" && -d "$pristine" && -d "$agent_artifacts" && -f "$executor_stdout" ]] || {
  echo "oracle inputs are missing" >&2
  exit 1
}
[[ "$(docker network inspect --format '{{.Internal}}' "$network")" == "true" ]] || {
  echo "oracle network must be Docker internal" >&2
  exit 1
}
oracle_image_id="$(docker image inspect --format '{{.Id}}' "$image")"
oracle_source_provenance="$(docker image inspect --format '{{index .Config.Labels "org.apache.hugegraph.ab.source-provenance"}}' "$oracle_image_id")"
oracle_runtime_bundle_sha256="$(docker image inspect --format '{{index .Config.Labels "org.apache.hugegraph.ab.runtime-bundle-sha256"}}' "$oracle_image_id")"
[[ "$oracle_source_provenance" == *":$expected_source_sha256"* ]] || {
  echo "oracle image is not bound to the current preflight source" >&2
  exit 1
}
[[ "$oracle_runtime_bundle_sha256" == "$expected_runtime_bundle_sha256" ]] || {
  echo "oracle image runtime bundle is stale" >&2
  exit 1
}

probe_uid=65534
probe_gid=65534
container="hg-ab-oracle-${run_id//[^A-Za-z0-9_.-]/-}-${RANDOM}"
seed_container="${container}-seed"
workspace_volume="${container}-workspace"
pristine_volume="${container}-pristine"
m2_volume="${container}-m2"
trusted_stage=""
workspace_volume_created=0
pristine_volume_created=0
m2_volume_created=0
cleanup_oracle() {
  local failed=0 name
  for name in "$container" "$seed_container"; do
    if docker container inspect "$name" >/dev/null 2>&1; then
      docker rm -f "$name" >/dev/null 2>&1 || failed=1
    fi
  done
  if ((workspace_volume_created == 1)) && docker volume inspect "$workspace_volume" >/dev/null 2>&1; then
    docker volume rm "$workspace_volume" >/dev/null 2>&1 || failed=1
  fi
  if ((pristine_volume_created == 1)) && docker volume inspect "$pristine_volume" >/dev/null 2>&1; then
    docker volume rm "$pristine_volume" >/dev/null 2>&1 || failed=1
  fi
  if ((m2_volume_created == 1)) && docker volume inspect "$m2_volume" >/dev/null 2>&1; then
    docker volume rm "$m2_volume" >/dev/null 2>&1 || failed=1
  fi
  [[ -z "$trusted_stage" ]] || rm -rf "$trusted_stage" || failed=1
  return "$failed"
}
finish_oracle() {
  local status=$?
  trap - EXIT
  cleanup_oracle || status=125
  exit "$status"
}
trap finish_oracle EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
trusted_stage="$(mktemp -d)"
mkdir -p "$trusted_stage/scripts" "$trusted_stage/agent-artifacts"
cp "$spec" "$trusted_stage/spec.json"
cp "$scripts_dir/trusted-command-oracle.py" "$scripts_dir/judge-run.py" "$trusted_stage/scripts/"
cp -a "$agent_artifacts/." "$trusted_stage/agent-artifacts/"
cp "$executor_stdout" "$trusted_stage/executor-stdout.txt"
chmod -R go-rwx "$trusted_stage/spec.json" "$trusted_stage/scripts"
chmod -R a-w "$trusted_stage/agent-artifacts" "$trusted_stage/executor-stdout.txt"
chmod -R a+rX "$trusted_stage/agent-artifacts" "$trusted_stage/executor-stdout.txt"
docker volume create "$workspace_volume" >/dev/null
workspace_volume_created=1
docker volume create "$pristine_volume" >/dev/null
pristine_volume_created=1
docker volume create "$m2_volume" >/dev/null
m2_volume_created=1

network_aliases=(--network-alias hg-ab-oracle)
if [[ "$case_id" == "server-hstore-graph-isolation" ]]; then
  network_aliases+=(--network-alias store --network-alias hugegraph)
fi

docker run --rm \
  --name "$seed_container" \
  --network none \
  --user 0:0 \
  --entrypoint /bin/sh \
  --mount "type=volume,src=$workspace_volume,dst=/workspace" \
  --mount "type=volume,src=$pristine_volume,dst=/pristine" \
  --mount "type=volume,src=$m2_volume,dst=/m2" \
  --mount "type=bind,src=$workspace,dst=/seed-workspace,readonly" \
  --mount "type=bind,src=$pristine,dst=/seed-pristine,readonly" \
  "$oracle_image_id" -c 'cp -a /seed-workspace/. /workspace/ && cp -a /seed-pristine/. /pristine/ && cp -a /opt/hg-ab/m2/. /m2/ && chown -R "$1:$2" /workspace /pristine /m2 && chmod -R u+rwX /m2' sh "$probe_uid" "$probe_gid"

docker create \
  --name "$container" \
  --network "$network" \
  "${network_aliases[@]}" \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --cap-drop ALL \
  --cap-add SETUID --cap-add SETGID --cap-add KILL --cap-add CHOWN \
  --security-opt no-new-privileges \
  --pids-limit "${HG_AB_PIDS_LIMIT:-1024}" \
  --memory "${HG_AB_MEMORY_LIMIT:-12g}" \
  --cpus "${HG_AB_CPU_LIMIT:-8}" \
  --user 0:0 \
  --mount "type=volume,src=$workspace_volume,dst=/ab/workspace" \
  --mount "type=bind,src=$workspace/version-evidence,dst=/ab/workspace/version-evidence,readonly" \
  --mount "type=volume,src=$pristine_volume,dst=/ab/pristine,readonly" \
  --mount "type=volume,src=$m2_volume,dst=/opt/hg-ab/m2" \
  --mount "type=bind,src=$trusted_stage/spec.json,dst=/oracle/spec.json,readonly" \
  --mount "type=bind,src=$trusted_stage/scripts,dst=/oracle/scripts,readonly" \
  --mount "type=bind,src=$trusted_stage/agent-artifacts,dst=/ab/agent-artifacts,readonly" \
  --mount "type=bind,src=$trusted_stage/executor-stdout.txt,dst=/ab/executor-stdout.txt,readonly" \
  --env HOME=/tmp \
  --env TMPDIR=/tmp \
  --env HTTP_PROXY= --env HTTPS_PROXY= --env ALL_PROXY= --env NO_PROXY='*' \
  --env http_proxy= --env https_proxy= --env all_proxy= --env no_proxy='*' \
  --env AB_CASE_ID="$case_id" \
  --env AB_RUN_ID="$run_id" \
  "$oracle_image_id" \
  python3 /oracle/scripts/trusted-command-oracle.py \
    --case "$case_id" --spec /oracle/spec.json \
    --workspace /ab/workspace --pristine /ab/pristine \
    --agent-artifacts /ab/agent-artifacts --executor-stdout /ab/executor-stdout.txt \
    --probe-uid "$probe_uid" --probe-gid "$probe_gid" \
    --output /tmp/evidence.json >/dev/null

set +e
docker start --attach "$container"
status=$?
set -e
if ((status != 0)); then
  exit "$status"
fi
docker cp "$container:/tmp/evidence.json" "$output"
printf '%s\n' "$oracle_image_id" >"${output}.oracle-image-id"
