#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -q 'ready'
if printf '%s' "$message" | grep -Eqi '\.goal-task|independent (read-only )?reviewer|独立.{0,4}(审查|评审|reviewer)'; then
  echo "普通文档目标不应引入 sidecar 或独立代码审查" >&2
  exit 1
fi
line_count="$(printf '%s\n' "$message" | wc -l | tr -d ' ')"
byte_count="$(printf '%s' "$message" | wc -c | tr -d ' ')"
test "$line_count" -le 34
test "$byte_count" -le 5000
