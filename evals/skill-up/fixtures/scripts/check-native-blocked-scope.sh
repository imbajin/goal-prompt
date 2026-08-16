#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi 'needs input|deferred|等待|延期'
printf '%s' "$message" | grep -Eqi 'api.*web|web.*api|独立.*(继续|工作)|continue.*independent'
printf '%s' "$message" | grep -Eqi '三次.*(重试|失败)|three.*(retries|failures)'
printf '%s' "$message" | grep -Eqi '三个.*goal turns|three.*goal turns|连续.*三个.*goal|consecutive.*three'
printf '%s' "$message" | grep -Eqi '所有剩余|all remaining|共同.*阻塞|jointly.*blocked'
printf '%s' "$message" | grep -Eqi 'update_goal|原生|native'
if printf '%s' "$message" | grep -Eqi 'worker[^。\n]*三次[^。\n]*(直接标记|直接将|then[^。\n]*blocked)|three retries[^.\n]*(directly|then)[^.\n]*overall blocked'; then
  echo "单项失败不得直接升级为整体 blocked" >&2
  exit 1
fi
