#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
normalized_message="${message//$'\n'/ }"
if printf '%s' "$normalized_message" | grep -Eqi '(不要|不应|无需|不需要|禁止|跳过|省略|绕过)[^。.]*(使用|运行)?[^。.]*(Chrome|browser[_ ]?use)|(Chrome|browser[_ ]?use)[^。.]*(可选|非必需|不是必须|无需|不需要|跳过|省略|绕过|建议而非硬性门槛|不是硬性门槛|非硬性门槛|非强制门槛|可不执行|仅为建议|只是建议|仅作建议|只是指导|推荐做法|不是硬性要求|非强制要求|不是验收门槛|optional|not required|not mandatory|not a (hard|required|mandatory) gate|may be (skipped|omitted|bypassed)|can be (skipped|omitted|bypassed)|suggestion rather than a gate|guidance rather than a gate|non-binding|merely a suggestion)|(skip|omit|bypass)[^.]*(Chrome|browser[_ ]?use)|do not[^.]*(use|run)[^.]*(Chrome|browser[_ ]?use)'; then
  echo "Chrome browser_use cannot be negated or optional" >&2
  exit 1
fi
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi 'Chrome|browser_use|browser use'
printf '%s' "$message" | grep -Eqi '成功[^。\n]*(失败|错误)|success[^.\n]*(failure|error)'
printf '%s' "$message" | grep -Eqi '截图|screenshot|browser evidence|浏览器证据|浏览器截图'
printf '%s' "$message" | grep -Eqi 'UI/UX'
printf '%s' "$message" | grep -Eqi '可访问性|accessibility'
printf '%s' "$message" | grep -Eqi '构建|build|DOM'
printf '%s' "$message" | grep -Eqi '不能.*(替代|代替)|不得.*(作为|当作)|not.*(replace|substitute)|instead'
