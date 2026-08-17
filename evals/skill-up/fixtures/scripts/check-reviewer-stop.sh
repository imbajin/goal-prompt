#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi '独立|independent'
printf '%s' "$message" | grep -Eqi '复审|re-review|review again'
printf '%s' "$message" | grep -Eqi '不可用|unavailable'
printf '%s' "$message" | grep -Eqi '继续[^。.\n]*(其余|不依赖|独立)|独立[^。.\n]*(继续|推进)|continue[^.\n]*(remaining|independent)|independent[^.\n]*(continue|proceed)'
printf '%s' "$message" | grep -Eqi '全部[^。.\n]*(阻塞|依赖)|所有[^。.\n]*(阻塞|依赖)|all[^.\n]*(blocked|depend)'
if printf '%s' "$message" | grep -Eqi \
  '停止所有|全部停止|不再复审|无需复审|stop all|do not re-review|no re-review'; then
  echo "Reviewer 暂不可用时不得停止独立工作或取消复审" >&2
  exit 1
fi
