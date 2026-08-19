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

[[ -n "$image" && -n "$network" && -n "$run_id" ]] || {
  echo "HG_AB_ORACLE_IMAGE, HG_AB_PRIVATE_NETWORK, and AB_RUN_ID are required" >&2
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

probe_uid=65534
probe_gid=65534
container="hg-ab-oracle-${run_id//[^A-Za-z0-9_.-]/-}-${RANDOM}"
seed_container="${container}-seed"
workspace_volume="${container}-workspace"
pristine_volume="${container}-pristine"
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
docker volume create "$pristine_volume" >/dev/null
cleanup_oracle() {
  docker rm -f "$container" "$seed_container" >/dev/null 2>&1 || true
  docker volume rm "$workspace_volume" "$pristine_volume" >/dev/null 2>&1 || true
  rm -rf "$trusted_stage"
}
trap cleanup_oracle EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

docker run --rm \
  --name "$seed_container" \
  --network none \
  --user 0:0 \
  --entrypoint /bin/sh \
  --mount "type=volume,src=$workspace_volume,dst=/workspace" \
  --mount "type=volume,src=$pristine_volume,dst=/pristine" \
  --mount "type=bind,src=$workspace,dst=/seed-workspace,readonly" \
  --mount "type=bind,src=$pristine,dst=/seed-pristine,readonly" \
  "$image" -c 'cp -a /seed-workspace/. /workspace/ && cp -a /seed-pristine/. /pristine/ && chown -R "$1:$2" /workspace /pristine' sh "$probe_uid" "$probe_gid"

docker create \
  --name "$container" \
  --network "$network" \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit "${HG_AB_PIDS_LIMIT:-1024}" \
  --memory "${HG_AB_MEMORY_LIMIT:-12g}" \
  --cpus "${HG_AB_CPU_LIMIT:-8}" \
  --user 0:0 \
  --mount "type=volume,src=$workspace_volume,dst=/ab/workspace" \
  --mount "type=volume,src=$pristine_volume,dst=/ab/pristine,readonly" \
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
  "$image" \
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
oracle_image_id="$(docker image inspect --format '{{.Id}}' "$image")"
printf '%s\n' "$oracle_image_id" >"${output}.oracle-image-id"
