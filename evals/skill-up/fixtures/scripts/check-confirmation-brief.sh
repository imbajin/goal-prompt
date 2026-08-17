#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
if printf '%s' "$message" | grep -Eq '(^|\n)[[:space:]]*/goal([[:space:]]|$)'; then
  echo "premature final goal" >&2
  exit 1
fi
printf '%s' "$message" | grep -Eqi '确认|confirm'
printf '%s' "$message" | grep -Eqi '范围|scope'
printf '%s' "$message" | grep -Eqi '证据|evidence|验证|validation'
