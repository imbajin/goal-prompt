#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi 'Chrome|browser_use|browser use'
printf '%s' "$message" | grep -Eqi '成功[^。\n]*(失败|错误)|success[^.\n]*(failure|error)'
printf '%s' "$message" | grep -Eqi '截图|screenshot|browser evidence'
printf '%s' "$message" | grep -Eqi 'UI/UX|可访问性|accessibility'
printf '%s' "$message" | grep -Eqi '构建|build|DOM'
printf '%s' "$message" | grep -Eqi '不能|不得|not|instead'
