#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -q 'state.md'
printf '%s' "$message" | grep -Eqi 'Progress|进度'
printf '%s' "$message" | grep -Eqi 'This loop|本轮|当前完成'
printf '%s' "$message" | grep -Eqi 'Remaining|剩余'
printf '%s' "$message" | grep -Eqi 'Next|下一步'
printf '%s' "$message" | grep -Eqi '(milestone|里程碑).*(commit|提交)|(commit|提交).*(milestone|里程碑)'
printf '%s' "$message" | grep -Eqi 'compaction|压缩|quota|配额|handoff|交接'
printf '%s' "$message" | grep -Eqi '(This loop|本轮|当前).*(completed|完成).*(item|事项|内容|工作|项)|完成事项|完成项|记录完成项|当前完成内容|本轮完成内容|已创建并验证|已完成[^。\n]*(事项|内容|工作|项)'
printf '%s' "$message" | grep -Eqi '(compaction|压缩|quota|配额|handoff|交接).*(state\.md|状态文件)|(state\.md|状态文件).*(compaction|压缩|quota|配额|handoff|交接)'
