#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
if printf '%s' "$message" | grep -Eq '(^|\n)[[:space:]]*/goal([[:space:]]|$)'; then
  echo "premature final goal" >&2
  exit 1
fi
# Accept semantic confirmation requests, not one fixed verb: a brief may ask
# the user to decide, choose, or provide the missing authorization.
printf '%s' "$message" | grep -Eqi '确认|决定|选择|需要你|请你|是否|confirm|decide|choose|please (confirm|decide|choose)'
printf '%s' "$message" | grep -Eqi '范围|scope'
printf '%s' "$message" | grep -Eqi '证据|evidence|验证|validation'
