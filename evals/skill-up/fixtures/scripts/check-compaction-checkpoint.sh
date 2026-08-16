#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -q 'state.md'
printf '%s' "$message" | grep -Eqi 'Progress|进度'
printf '%s' "$message" | grep -Eqi 'This loop|本轮|当前完成'
printf '%s' "$message" | grep -Eqi 'Remaining|剩余'
printf '%s' "$message" | grep -Eqi 'Next|下一步'
printf '%s' "$message" | grep -Eqi 'commit|提交'
printf '%s' "$message" | grep -Eqi 'compaction|压缩|quota|配额|handoff|交接'
printf '%s' "$message" | grep -Eqi '完成[^。\n]*(state|事项|终态)|完整终态|completed[^.\n]*(state|items)'
