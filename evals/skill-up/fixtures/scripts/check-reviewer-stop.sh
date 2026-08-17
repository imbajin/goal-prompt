#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi '独立|independent|不依赖'
printf '%s' "$message" | grep -Eqi '复审|复核|重新审查|再次审查|重新评审|再次评审|re-?review|review again'
printf '%s' "$message" | grep -Eqi '不可用|unavailable'
printf '%s' "$message" | grep -Eqi '继续[^。.\n]*(其余|不依赖|独立|independent|源码分析|工作)|独立[^。.\n]*(继续|推进)|[^。.\n]*(可以|能够|可)[^。.\n]*(继续|推进)[^。.\n]*(工作|分析)|continue[^.\n]*(remaining|independent|analysis|work)|independent[^.\n]*(continue|proceed)'
printf '%s' "$message" | grep -Eqi '全部[^。.\n]*(阻塞|依赖)|所有[^。.\n]*(阻塞|依赖)|唯一剩余[^。.\n]*(门禁|依赖|阻塞|gate)|all[^.\n]*(blocked|depend)|only remaining[^.\n]*(gate|depend|block)'
if printf '%s' "$message" | grep -Eqi \
  '停止所有|全部停止|不再复审|无需复审|stop all|do not re-review|no re-review'; then
  echo "Reviewer 暂不可用时不得停止独立工作或取消复审" >&2
  exit 1
fi
