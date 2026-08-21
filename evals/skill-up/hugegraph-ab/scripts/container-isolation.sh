#!/usr/bin/env bash
set -euo pipefail

if (($# != 4)); then
  echo "usage: container-isolation.sh EXECUTOR GOAL WORKSPACE AGENT_ARTIFACTS" >&2
  exit 2
fi

executor="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
goal="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
workspace="$(cd "$3" && pwd)"
agent_artifacts="$(cd "$4" && pwd)"
stage="${AB_STAGE_ROOT:-}"
attestation="${AB_ISOLATION_ATTESTATION:-}"
service_attestation="${HG_AB_SERVICE_ATTESTATION:-}"
image="${HG_AB_EXECUTOR_IMAGE:-}"
network="${HG_AB_PRIVATE_NETWORK:-}"
model_base_url="${HG_AB_MODEL_BASE_URL:-}"
model_policy_url="${HG_AB_MODEL_POLICY_URL:-}"
model_policy_identity="${HG_AB_MODEL_POLICY_IDENTITY:-}"
model_api_key="${HG_AB_MODEL_API_KEY:-}"
private_health_urls="${HG_AB_PRIVATE_HEALTH_URLS:-}"
service_config_identity="${HG_AB_SERVICE_CONFIG_IDENTITY:-}"
expected_source_sha256="${HG_AB_SOURCE_SHA256:-}"
expected_runtime_bundle_sha256="${HG_AB_RUNTIME_BUNDLE_SHA256:-}"
scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
network_probe="$scripts_dir/container-network-probe.py"

[[ -n "$stage" && -n "$attestation" && -n "$service_attestation" && -n "$image" && -n "$network" ]] || {
  echo "stage, attestation, service attestation, executor image, and private network are required" >&2
  exit 1
}
[[ -n "$model_base_url" && -n "$model_policy_url" && -n "$model_policy_identity" && -n "$model_api_key" ]] || {
  echo "model endpoint, policy, identity, and API key are required" >&2
  exit 1
}
[[ -n "$private_health_urls" && -n "$service_config_identity" && -n "$expected_source_sha256" && -n "$expected_runtime_bundle_sha256" ]] || {
  echo "private service health URLs and service config identity are required" >&2
  exit 1
}
stage="$(cd "$stage" && pwd)"
[[ "$goal" == "$stage/session/generated-goal.txt" ]] || {
  echo "goal must be the current arm session/generated-goal.txt" >&2
  exit 1
}
[[ "$agent_artifacts" == "$stage/agent-artifacts" ]] || {
  echo "executor output must be the current arm's agent-artifacts directory" >&2
  exit 1
}
[[ "$attestation" == "$stage/artifacts/isolation-attestation.json" ]] || {
  echo "trusted isolation attestation must stay outside agent-artifacts" >&2
  exit 1
}

for path in "$goal" "$workspace" "$agent_artifacts" "$attestation" "$service_attestation"; do
  case "$path" in
    "$stage"/*) ;;
    *) echo "all arm paths must be inside AB_STAGE_ROOT" >&2; exit 1 ;;
  esac
done

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
[[ -x "$executor" && -x "$network_probe" ]] || { echo "executor/network probe is not executable" >&2; exit 1; }
[[ -f "$service_attestation" ]] || { echo "service attestation is missing" >&2; exit 1; }
[[ "$(docker network inspect --format '{{.Internal}}' "$network")" == "true" ]] || {
  echo "HG_AB_PRIVATE_NETWORK must be a Docker internal network" >&2
  exit 1
}

image_id="$(docker image inspect --format '{{.Id}}' "$image")"
image_source_provenance="$(docker image inspect --format '{{index .Config.Labels "org.apache.hugegraph.ab.source-provenance"}}' "$image_id")"
image_runtime_bundle_sha256="$(docker image inspect --format '{{index .Config.Labels "org.apache.hugegraph.ab.runtime-bundle-sha256"}}' "$image_id")"
[[ "$image_source_provenance" == *":$expected_source_sha256"* ]] || {
  echo "executor image is not bound to the current preflight source" >&2
  exit 1
}
[[ "$image_runtime_bundle_sha256" == "$expected_runtime_bundle_sha256" ]] || {
  echo "executor image runtime bundle is stale" >&2
  exit 1
}
network_id="$(docker network inspect --format '{{.Id}}' "$network")"
service_attestation_sha256="$(python3 -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$service_attestation")"
service_image_ids="$(python3 -c 'import json, pathlib, sys; value=json.loads(pathlib.Path(sys.argv[1]).read_text()); print(json.dumps(value.get("service_image_ids", {}), sort_keys=True, separators=(",", ":")))' "$service_attestation")"
service_artifact_ids="$(python3 -c 'import json, pathlib, sys; value=json.loads(pathlib.Path(sys.argv[1]).read_text()); print(json.dumps(value.get("service_artifact_ids", {}), sort_keys=True, separators=(",", ":")))' "$service_attestation")"
provider_origin_sha256="$(python3 -c 'import json, pathlib, sys; value=json.loads(pathlib.Path(sys.argv[1]).read_text()); print(value.get("provider_origin_sha256", ""))' "$service_attestation")"
uid="$(id -u)"
gid="$(id -g)"
container_goal="/ab/session/generated-goal.txt"
container_workspace="/ab/workspace"
container_artifacts="/ab/agent-artifacts"
safe_run_id="${AB_RUN_ID//[^A-Za-z0-9_.-]/-}"
volume="hg-ab-workspace-${safe_run_id}-${RANDOM}"
container_prefix="hg-ab-${safe_run_id}-${RANDOM}"
probe_container="${container_prefix}-probe"
seed_container="${container_prefix}-seed"
main_container="${container_prefix}-agent"
copy_container="${container_prefix}-copy"
volume_created=0
cleanup_runtime() {
  local failed=0 name
  for name in "$probe_container" "$seed_container" "$main_container" "$copy_container"; do
    if docker container inspect "$name" >/dev/null 2>&1; then
      docker rm -f "$name" >/dev/null 2>&1 || failed=1
    fi
  done
  if ((volume_created == 1)) && docker volume inspect "$volume" >/dev/null 2>&1; then
    docker volume rm "$volume" >/dev/null 2>&1 || failed=1
  fi
  return "$failed"
}
finish_runtime() {
  local status=$?
  trap - EXIT
  cleanup_runtime || status=125
  exit "$status"
}
trap finish_runtime EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
docker volume create "$volume" >/dev/null
volume_created=1

# Probe from the exact internal network before any model task runs.
docker run --rm \
  --name "$probe_container" \
  --network "$network" \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --mount "type=bind,src=$network_probe,dst=/probe/network.py,readonly" \
  --env HTTP_PROXY= --env HTTPS_PROXY= --env ALL_PROXY= --env NO_PROXY='*' \
  --env http_proxy= --env https_proxy= --env all_proxy= --env no_proxy='*' \
  --env OPENAI_API_KEY="$model_api_key" \
  "$image_id" python3 /probe/network.py \
    --model-base-url "$model_base_url" \
    --policy-url "$model_policy_url" \
    --policy-identity "$model_policy_identity" \
    --health-urls-json "$private_health_urls" >/dev/null

docker run --rm \
  --name "$seed_container" \
  --network none \
  --user 0:0 \
  --entrypoint /bin/sh \
  --mount "type=volume,src=$volume,dst=/work" \
  --mount "type=bind,src=$workspace,dst=/seed,readonly" \
  "$image_id" -c 'cp -a /seed/. /work/ && chown -R "$1:$2" /work' sh "$uid" "$gid"

mounts=(
  --mount "type=bind,src=$stage/home,dst=/ab/home"
  --mount "type=bind,src=$stage/session,dst=/ab/session"
  --mount "type=bind,src=$goal,dst=$container_goal,readonly"
  --mount "type=bind,src=$stage/data,dst=/ab/data"
  --mount "type=bind,src=$agent_artifacts,dst=/ab/agent-artifacts"
  --mount "type=volume,src=$volume,dst=$container_workspace"
  --mount "type=bind,src=$workspace/version-evidence,dst=$container_workspace/version-evidence,readonly"
  --mount "type=bind,src=$executor,dst=/runner/executor,readonly"
)
network_aliases=()
if [[ "${AB_CASE_ID:-}" == "server-hstore-graph-isolation" ]]; then
  network_aliases=(--network-alias store --network-alias hugegraph)
fi

set +e
docker run --rm \
  --name "$main_container" \
  --network "$network" \
  "${network_aliases[@]}" \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit "${HG_AB_PIDS_LIMIT:-1024}" \
  --memory "${HG_AB_MEMORY_LIMIT:-12g}" \
  --cpus "${HG_AB_CPU_LIMIT:-8}" \
  --user "$uid:$gid" \
  "${mounts[@]}" \
  --env HOME=/ab/home \
  --env TMPDIR=/ab/session \
  --env AB_SESSION_DIR=/ab/session \
  --env AB_DATA_DIR=/ab/data \
  --env AB_RUN_ID="${AB_RUN_ID:-}" \
  --env AB_CASE_ID="${AB_CASE_ID:-}" \
  --env AB_MODEL="${AB_MODEL:-}" \
  --env AB_REASONING_EFFORT="${AB_REASONING_EFFORT:-}" \
  --env HG_AB_HUGEGRAPH_URL=http://hugegraph:8080 \
  --env HG_AB_HUGEGRAPH_USER=admin \
  --env HG_AB_HUGEGRAPH_PASSWORD=hg-ab-isolated-admin \
  --env HG_AB_PD_URL=http://pd:8620 \
  --env HTTP_PROXY= --env HTTPS_PROXY= --env ALL_PROXY= --env NO_PROXY='*' \
  --env http_proxy= --env https_proxy= --env all_proxy= --env no_proxy='*' \
  --env OPENAI_BASE_URL="$model_base_url" \
  --env OPENAI_API_KEY="$model_api_key" \
  "$image_id" \
  /runner/executor "$container_goal" "$container_workspace" "$container_artifacts"
status=$?
set -e

copy_failed=0
if ! docker run --rm \
  --name "$copy_container" \
  --network none \
  --user 0:0 \
  --entrypoint /bin/sh \
  --mount "type=volume,src=$volume,dst=/work,readonly" \
  --mount "type=bind,src=$workspace,dst=/host" \
  "$image_id" -c 'find /host -mindepth 1 -maxdepth 1 ! -name version-evidence -exec rm -rf {} + && find /work -mindepth 1 -maxdepth 1 ! -name version-evidence -exec cp -a {} /host/ \;'
then
  echo "failed to copy isolated workspace back to host" >&2
  copy_failed=1
  status=125
fi

wrapper_failure_kind=""
if ((copy_failed == 1)); then
  wrapper_failure_kind="copy_back_error"
elif ((status == 125 || status == 126 || status == 127)); then
  wrapper_failure_kind="container_runtime_error"
fi

python3 -c '
import json, pathlib, sys
(output, image_id, network_id, service_sha, policy_identity,
 config_identity, model_base_url, source_provenance, status,
 wrapper_failure_kind, service_images, service_artifacts, provider_origin) = sys.argv[1:]
pathlib.Path(output).write_text(json.dumps({
    "schema_version": 2,
    "runtime": "docker_internal_network",
    "filesystem_isolated": True,
    "process_isolated": True,
    "stage_root_only": True,
    "trusted_artifacts_not_mounted": True,
    "version_evidence_read_only_mount": True,
    "public_egress_denied": True,
    "private_services_allowed": True,
    "model_proxy_only": True,
    "network_probe_passed": True,
    "container_image_id": image_id,
    "private_network_id": network_id,
    "service_attestation_sha256": service_sha,
    "model_policy_identity": policy_identity,
    "model_base_url": model_base_url,
    "service_config_identity": config_identity,
    "image_source_provenance": source_provenance,
    "service_image_ids": json.loads(service_images),
    "service_artifact_ids": json.loads(service_artifacts),
    "provider_origin_sha256": provider_origin,
    "executor_exit_code": int(status),
    "wrapper_failure_kind": wrapper_failure_kind or None,
}, indent=2) + "\n", encoding="utf-8")
' "$attestation" "$image_id" "$network_id" "$service_attestation_sha256" "$model_policy_identity" "$service_config_identity" "$model_base_url" "$image_source_provenance" "$status" "$wrapper_failure_kind" "$service_image_ids" "$service_artifact_ids" "$provider_origin_sha256"

exit "$status"
