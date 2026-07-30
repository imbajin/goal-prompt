#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -q '.goal-task/auth-migration/state.md'
printf '%s' "$message" | grep -Eqi '独立|independent'
printf '%s' "$message" | grep -Eqi '复审|re-review|review again'
printf '%s' "$message" | grep -Eqi '阻塞|blocked'
printf '%s' "$message" | grep -Eqi 'CI'
