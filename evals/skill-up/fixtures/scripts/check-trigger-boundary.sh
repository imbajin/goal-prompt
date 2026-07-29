#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -Eqi 'teh|the|README'
if printf '%s\n' "$message" | grep -Eq '^[[:space:]]*/goal[[:space:]]'; then
  echo "普通任务被错误地转成了 /goal" >&2
  exit 1
fi
if printf '%s' "$message" | grep -Eq 'needs confirmation|(^|[[:space:]])ready$'; then
  echo "普通任务不应进入 goal-prompt 两阶段协议" >&2
  exit 1
fi
