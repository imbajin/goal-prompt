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
printf '%s' "$message" | grep -q 'state.md'
printf '%s' "$message" | grep -Eqi 'Progress|进度'
printf '%s' "$message" | grep -Eqi 'This loop|本轮|当前完成'
printf '%s' "$message" | grep -Eqi 'Remaining|剩余'
printf '%s' "$message" | grep -Eqi 'Next|下一步'
printf '%s' "$message" | grep -Eqi '(milestone|里程碑).*(commit|提交)|(commit|提交).*(milestone|里程碑)'
printf '%s' "$message" | grep -Eqi 'compaction|压缩|quota|配额|handoff|交接'
printf '%s' "$message" | grep -Eqi '(This loop|本轮|当前).*(completed|完成).*(item|事项|内容|工作|项)|完成事项|完成项|记录完成项|当前完成内容|本轮完成内容|已创建并验证|已完成[^。\n]*(事项|内容|工作|项)'
printf '%s' "$message" | grep -Eqi '(compaction|压缩|quota|配额|handoff|交接).*(state\.md|状态文件)|(state\.md|状态文件).*(compaction|压缩|quota|配额|handoff|交接)'
