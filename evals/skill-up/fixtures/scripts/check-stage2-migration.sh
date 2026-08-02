#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -q '.goal-task/auth-migration/state.md'
printf '%s' "$message" | grep -Eqi '独立|independent'
printf '%s' "$message" | grep -Eqi '复审|re-review|review again'
printf '%s' "$message" | grep -Eqi '阻塞|blocked'
printf '%s' "$message" | grep -Eqi 'CI'
printf '%s' "$message" | grep -Eqi '兼容|compatib'
printf '%s' "$message" | grep -Eqi '全部|所有|all'
printf '%s' "$message" | grep -Eqi '其余|独立工作|remaining|independent work'
if printf '%s' "$message" | grep -Eqi \
  '一个[^。.\n]*(等待|失败)[^。.\n]*(整体|全局)[^。.\n]*(阻塞|停止)|one[^.\n]*(wait|fail)[^.\n]*(overall|global)[^.\n]*(blocked|stop)'; then
  echo "单个等待或失败不得让整体目标提前阻塞" >&2
  exit 1
fi
