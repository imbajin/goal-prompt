#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi '仓库|repository|repo|未知|unknown|执行时|during execution'
if printf '%s' "$message" | grep -Eqi '请提供.*仓库|provide.*repository|无法安全开始'; then
  echo "delegation stopped instead of rendering an honest goal" >&2
  exit 1
fi
