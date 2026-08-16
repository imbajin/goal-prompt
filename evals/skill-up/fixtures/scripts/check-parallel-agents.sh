#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi 'auth'
printf '%s' "$message" | grep -Eqi 'billing'
printf '%s' "$message" | grep -Eqi 'notifications'
printf '%s' "$message" | grep -Eqi 'ownership|owner|所有权|归属'
printf '%s' "$message" | grep -Eqi 'schema|lockfile|共享.*(唯一|owner)|single owner'
printf '%s' "$message" | grep -Eqi 'integrat|接缝|集成'
printf '%s' "$message" | grep -Eqi 're-run|rerun|复跑|复验|重新运行|重跑|再次运行'
printf '%s' "$message" | grep -Eqi 'independent reviewer|独立.*reviewer|独立.*审查'
