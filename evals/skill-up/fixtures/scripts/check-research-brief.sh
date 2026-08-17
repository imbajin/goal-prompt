#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
if printf '%s' "$message" | grep -Eq '(^|\n)[[:space:]]*/goal([[:space:]]|$)'; then
  echo "premature final goal" >&2
  exit 1
fi
if printf '%s' "$message" | grep -Eqi '不是只读|不只读|not[[:space:]-]+read[[:space:]-]+only'; then
  echo "explicitly non-read-only" >&2
  exit 1
fi
printf '%s' "$message" | grep -Eqi '只读|read-only|read only|不修改|不实现|不写入|不落盘|仅分析|仅报告|report-only'
printf '%s' "$message" | grep -Eqi '证据|evidence|引用|source'
printf '%s' "$message" | grep -Eqi '偏好|preference|决定|decision|未知|unknown|缺失|missing'
if printf '%s' "$message" | grep -Eqi '(行为变更|code|implementation|实现)[[:space:]]+reviewer[^。\n]*(必须|门槛|要求|required|must)'; then
  if ! printf '%s' "$message" | grep -Eqi '(不作为|不应作为|不宜作为|不自动|不默认|不是默认|不应机械|不机械|无需|不需要|非默认|not[[:space:]]+(a[[:space:]]+)?default|not[[:space:]]+required|without[[:space:]]+a)'; then
    echo "mechanical implementation reviewer gate" >&2
    exit 1
  fi
fi
