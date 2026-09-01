#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
goal_count="$(printf '%s\n' "$message" | grep -Ec '^[[:space:]]*/goal([[:space:]]|$)' || true)"
[[ "$goal_count" -eq 1 ]] || { echo "expected exactly one rendered /goal" >&2; exit 1; }
goal_body="$(
  printf '%s\n' "$message" | awk '
    function strip_prefix(line) {
      sub(/^[[:space:]]*\/goal([[:space:]]|$)/, "", line)
      sub(/^[[:space:]]+/, "", line)
      return line
    }
    BEGIN { fenced = 0; found = 0; mode = "" }
    {
      if (fenced) {
        if ($0 ~ /^[[:space:]]*```/) {
          if (found) exit
          fenced = 0
          next
        }
        if (!found && $0 ~ /^[[:space:]]*\/goal([[:space:]]|$)/) {
          found = 1
          body = strip_prefix($0)
          next
        }
        if (found) body = body "\n" $0
        next
      }
      if ($0 ~ /^[[:space:]]*```/) {
        fenced = 1
        next
      }
      if (!found && $0 ~ /^[[:space:]]*\/goal([[:space:]]|$)/) {
        found = 1
        mode = "direct"
        body = strip_prefix($0)
        next
      }
      if (found && mode == "direct") {
        if ($0 ~ /^[[:space:]]*(Explanation|Notes?|说明|备注)[[:space:]]*[:：]/) exit
        body = body "\n" $0
      }
    }
    END {
      if (!found) exit 1
      print body
    }
  '
)" || {
  echo "final /goal body not found" >&2
  exit 1
}
normalized_message="${goal_body//$'\n'/ }"
if printf '%s' "$normalized_message" | grep -Eqi '(不要|不应|无需|不需要|禁止|跳过|省略|绕过)[^。.]*(使用|运行)?[^。.]*(Chrome|browser[_ ]?use)|(Chrome|browser[_ ]?use)[^。.]*(可选|非必需|不是必须|无需|不需要|跳过|省略|绕过|建议而非硬性门槛|不是硬性门槛|非硬性门槛|非强制门槛|可不执行|仅为建议|只是建议|仅作建议|只是指导|推荐做法|不是硬性要求|非强制要求|不是验收门槛|optional|not required|not mandatory|not a (hard|required|mandatory) gate|may be (skipped|omitted|bypassed)|can be (skipped|omitted|bypassed)|suggestion rather than a gate|guidance rather than a gate|non-binding|merely a suggestion)|(skip|omit|bypass)[^.]*(Chrome|browser[_ ]?use)|do not[^.]*(use|run)[^.]*(Chrome|browser[_ ]?use)'; then
  echo "Chrome browser_use cannot be negated or optional" >&2
  exit 1
fi
printf '%s' "$normalized_message" | grep -Eqi 'Chrome|browser_use|browser use'
printf '%s' "$normalized_message" | grep -Eqi '成功.*(失败|错误)|(失败|错误).*成功|success.*(failure|error)|(failure|error).*success'
printf '%s' "$normalized_message" | grep -Eqi '截图|screenshot|browser evidence|浏览器证据|浏览器截图'
printf '%s' "$normalized_message" | grep -Eqi 'UI/UX'
printf '%s' "$normalized_message" | grep -Eqi '可访问性|accessibility'
printf '%s' "$normalized_message" | grep -Eqi '构建|build|DOM'
printf '%s' "$normalized_message" | grep -Eqi '不能.*(替代|代替)|不得.*(作为|当作)|not.*(replace|substitute)|instead'
