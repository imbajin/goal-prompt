#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
if printf '%s' "$message" | grep -Eqi \
  '\.goal-task/[^[:space:]`]+/(state|todo|design|lessons)\.md|([234]|多个|多名)[[:space:]]*(个|名)?[[:space:]]*(独立)?[[:space:]]*(reviewer|reviewers|审查者|评审)|exactly[[:space:]]+[234]'; then
  echo "普通文档目标不应引入 sidecar 或多个 reviewer 门槛" >&2
  exit 1
fi
line_count="$(printf '%s\n' "$message" | wc -l | tr -d ' ')"
byte_count="$(printf '%s' "$message" | wc -c | tr -d ' ')"
test "$line_count" -le 34
test "$byte_count" -le 5000
