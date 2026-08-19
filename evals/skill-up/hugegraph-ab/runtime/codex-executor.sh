#!/usr/bin/env bash
set -euo pipefail

if (($# != 3)); then
  echo "usage: codex-executor.sh GOAL WORKSPACE AGENT_ARTIFACTS" >&2
  exit 2
fi

goal="$1"
workspace="$2"
artifacts="$3"

[[ -f "$goal" && -d "$workspace" && -d "$artifacts" ]] || {
  echo "executor inputs are missing" >&2
  exit 125
}
[[ -n "${AB_MODEL:-}" && -n "${AB_REASONING_EFFORT:-}" ]] || {
  echo "AB_MODEL and AB_REASONING_EFFORT are required" >&2
  exit 125
}
command -v codex >/dev/null 2>&1 || {
  echo "codex CLI is missing from the reviewed image" >&2
  exit 125
}

# Dependencies are baked into the reviewed image because the Agent network has
# no package-registry egress.  Symlinks are per-arm and point only at immutable
# image content; all project outputs still land in the disposable workspace.
if [[ -f "$workspace/hugegraph-hubble/hubble-fe/yarn.lock" \
      && ! -e "$workspace/hugegraph-hubble/hubble-fe/node_modules" ]]; then
  ln -s /opt/hg-ab/toolchain-node_modules \
    "$workspace/hugegraph-hubble/hubble-fe/node_modules"
fi
if [[ -f "$workspace/package.json" && -d "$workspace/content" \
      && ! -e "$workspace/node_modules" ]]; then
  ln -s /opt/hg-ab/docs-node_modules "$workspace/node_modules"
fi

final="$artifacts/final-response.txt"
events="$artifacts/codex-events.jsonl"

# The generated /goal is passed byte-for-byte on stdin.  The container is the
# security boundary; Codex therefore receives full workspace access without a
# second interactive approval layer.  A generic CLI failure remains an
# environment error (not a trusted model zero) by preserving its exit code.
set +e
codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  --skip-git-repo-check \
  --ephemeral \
  --ignore-user-config \
  --ignore-rules \
  --color never \
  --json \
  --model "$AB_MODEL" \
  --config "model_reasoning_effort=\"$AB_REASONING_EFFORT\"" \
  --cd "$workspace" \
  --output-last-message "$final" \
  - <"$goal" >"$events"
status=$?
set -e

if ((status != 0)); then
  exit "$status"
fi
[[ -s "$final" ]] || {
  echo "codex completed without a final response" >&2
  exit 125
}

exit 0
