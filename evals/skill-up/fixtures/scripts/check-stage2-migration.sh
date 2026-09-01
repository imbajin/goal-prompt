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
printf '%s' "$message" | grep -q '.goal-task/auth-migration/state.md'
printf '%s' "$message" | grep -Eqi '独立|independent'
printf '%s' "$message" | grep -Eqi '复审|复核|重新审查|再次审查|重新评审|再次评审|re-?review|review again'
printf '%s' "$message" | grep -Eqi '阻塞|blocked'
printf '%s' "$message" | grep -Eqi 'CI'
printf '%s' "$message" | grep -Eqi '兼容|compatib'
printf '%s' "$message" | grep -Eqi '全部|所有|all'
printf '%s' "$message" | grep -Eqi '其余|独立工作|不依赖|可继续|继续执行|remaining|independent work|unblocked|continue'
if printf '%s' "$message" | grep -Eqi \
  '一个[^。.\n]*(等待|失败)[^。.\n]*(整体|全局)[^。.\n]*(阻塞|停止)|one[^.\n]*(wait|fail)[^.\n]*(overall|global)[^.\n]*(blocked|stop)'; then
  echo "单个等待或失败不得让整体目标提前阻塞" >&2
  exit 1
fi
