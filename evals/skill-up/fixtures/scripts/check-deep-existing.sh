#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi 'docs/requirement\.md'
printf '%s' "$message" | grep -Eqi 'docs/design\.md'
printf '%s' "$message" | grep -Eqi 'docs/todo\.md'
printf '%s' "$message" | grep -Eqi 'deep|深度|state\.md'
printf '%s' "$message" | grep -Eqi '恢复|recovery|重排|repriorit|independent work'
printf '%s' "$message" | grep -Eqi '3.*reviewer|three.*reviewer|三个.*reviewer'
