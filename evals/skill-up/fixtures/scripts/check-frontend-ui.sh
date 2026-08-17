#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi 'Chrome|browser_use|browser use'
printf '%s' "$message" | grep -Eqi '成功[^。\n]*(失败|错误)|success[^.\n]*(failure|error)'
printf '%s' "$message" | grep -Eqi '截图|screenshot|browser evidence|浏览器证据|浏览器截图'
printf '%s' "$message" | grep -Eqi 'UI/UX'
printf '%s' "$message" | grep -Eqi '可访问性|accessibility'
printf '%s' "$message" | grep -Eqi '构建|build|DOM'
printf '%s' "$message" | grep -Eqi '不能.*(替代|代替)|不得.*(作为|当作)|not.*(replace|substitute)|instead'
