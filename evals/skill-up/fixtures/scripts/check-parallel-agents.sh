#!/usr/bin/env bash
set -euo pipefail
message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi 'auth'
printf '%s' "$message" | grep -Eqi 'billing'
printf '%s' "$message" | grep -Eqi 'notifications'
printf '%s' "$message" | grep -Eqi 'ownership|owner|所有权|归属'
printf '%s' "$message" | grep -Eqi '(schema|lockfile|共享).*(single owner|唯一 owner|唯一归属|唯一拥有|独占|唯一负责人|唯一负责|唯一可修改|唯一的共享)|(single owner|唯一 owner|唯一归属|唯一拥有|独占|唯一负责人|唯一负责|唯一可修改|唯一的共享).*(schema|lockfile|共享)'
printf '%s' "$message" | grep -Eqi '(integrat|接缝|集成).*(re-run|rerun|复跑|复验|重新运行|重跑|再次运行)|(re-run|rerun|复跑|复验|重新运行|重跑|再次运行).*(integrat|接缝|集成)'
printf '%s' "$message" | grep -Eqi 'independent reviewer|独立.*(reviewer|审查|评审)'
