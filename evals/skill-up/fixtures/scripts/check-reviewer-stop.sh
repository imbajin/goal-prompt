#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
printf '%s' "$message" | grep -q '/goal'
printf '%s' "$message" | grep -Eqi '独立|independent'
printf '%s' "$message" | grep -Eqi '复审|re-review|review again'
printf '%s' "$message" | grep -Eqi '不可用|unavailable'
printf '%s' "$message" | grep -Eqi '其余|不依赖|review-independent|remaining'
printf '%s' "$message" | grep -Eqi '停止|stop|blocked'
