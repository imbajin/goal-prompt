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
message="$goal_body"
printf '%s' "$message" | grep -Eqi 'needs input|deferred|等待|延期'
printf '%s' "$message" | grep -Eqi 'api.*web|web.*api|独立.*(继续|工作)|continue.*independent'
printf '%s' "$message" | grep -Eqi '三次.*(重试|失败)|three.*(retries|failures)'
printf '%s' "$message" | grep -Eqi '三个.*goal turns|three.*goal turns|连续.*三个.*goal|consecutive.*three'
printf '%s' "$message" | grep -Eqi '所有剩余|所有有意义的剩余|所有.*工作.*依赖|all remaining|共同.*阻塞|共同.*无法推进|jointly.*blocked'
if printf '%s' "$message" | grep -Eqi '阻塞[^。.]*(不同|不相同|各不相同)|blockers?[^.]*(differ|different|vary)|different blockers|blockers are different'; then
  echo "整体 blocked 必须由同一个共同 blocker 导致" >&2
  exit 1
fi
printf '%s' "$message" | grep -Eqi '所有(有意义的)?剩余[^。.]*(同一|同一个|相同|共同的)[^。.]*(条件|原因|阻塞|依赖|门槛|问题)|(同一|同一个|相同|共同的)[^。.]*(条件|原因|阻塞|依赖|门槛|问题)[^。.]*(所有(有意义的)?剩余)|all remaining[^.]*(same|shared|common)[^.]*(condition|blocker|dependency|gate|reason)|(same|shared|common)[^.]*(condition|blocker|dependency|gate|reason)[^.]*all remaining'
printf '%s' "$message" | grep -Eqi 'update_goal|原生|native'
if printf '%s' "$message" | grep -Eqi 'worker[^。\n]*三次[^。\n]*(直接标记|直接将|then[^。\n]*blocked)|three retries[^.\n]*(directly|then)[^.\n]*overall blocked'; then
  echo "单项失败不得直接升级为整体 blocked" >&2
  exit 1
fi
