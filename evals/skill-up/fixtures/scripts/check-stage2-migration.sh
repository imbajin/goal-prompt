#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
goal_count="$(printf '%s\n' "$message" | grep -Ec '^[[:space:]]*/goal([[:space:]]|$)' || true)"
[[ "$goal_count" -eq 1 ]] || { echo "expected exactly one rendered /goal" >&2; exit 1; }
goal_body="$(
  printf '%s\n' "$message" | awk '
    function strip_prefix(line) {
      sub(/^[[:space:]]*\/goal([[:space:]]|$)/, "", line)
      sub(/^[[:space:]]+/, "", line)
      return line
    }
    BEGIN { fenced = 0; found = 0; mode = "" }
    {
      if (fenced) {
        if ($0 ~ /^[[:space:]]*```/) {
          if (found) exit
          fenced = 0
          next
        }
        if (!found && $0 ~ /^[[:space:]]*\/goal([[:space:]]|$)/) {
          found = 1
          body = strip_prefix($0)
          next
        }
        if (found) body = body "\n" $0
        next
      }
      if ($0 ~ /^[[:space:]]*```/) {
        fenced = 1
        next
      }
      if (!found && $0 ~ /^[[:space:]]*\/goal([[:space:]]|$)/) {
        found = 1
        mode = "direct"
        body = strip_prefix($0)
        next
      }
      if (found && mode == "direct") {
        if ($0 ~ /^[[:space:]]*(Explanation|Notes?|说明|备注)[[:space:]]*[:：]/) exit
        body = body "\n" $0
      }
    }
    END {
      if (!found) exit 1
      print body
    }
  '
)" || {
  echo "final /goal body not found" >&2
  exit 1
}
message="$goal_body"
printf '%s' "$message" | grep -q '.goal-task/auth-migration/state.md'
printf '%s' "$message" | grep -Eqi '独立|independent'
printf '%s' "$message" | grep -Eqi '复审|复核|重新审查|再次审查|重新评审|再次评审|re-?review|review again'
printf '%s' "$message" | grep -Eqi '阻塞|blocked'
printf '%s' "$message" | grep -Eqi 'CI'
printf '%s' "$message" | grep -Eqi '兼容|compatib'
printf '%s' "$message" | grep -Eqi '全部|所有|all'
printf '%s' "$message" | grep -Eqi '其余|独立(推进)?的?工作|不依赖|可继续|继续执行|remaining|independent work|unblocked|continue'
# Mentioning independent work does not establish that it should continue.
# Check only the local clause; a prohibition on stopping it has the opposite
# meaning from a prohibition on continuing it.
EVAL_FINAL_MESSAGE="$message" python3 - <<'PY'
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
scope = re.compile(
    r"(?:独立|其余|不依赖)[^，,。；;\n]{0,24}(?:工作|事项|任务)"
    r"|(?:independent|unblocked)\s+(?:work|tasks?)",
    re.IGNORECASE,
)
negative = (
    r"(?:不(?:应(?:该)?|要|得|能|会|可(?:以)?|必|再)?|无需|禁止|严禁"
    r"|never|do\s+not|must\s+not|should\s+not|cannot|avoid)"
)
continuation = r"(?:继续|推进|执行|处理|continue|progress|proceed(?:\s+with)?|execute|work\s+on)"
negative_continuation = re.compile(negative + r"\s*(?:再\s*)?" + continuation, re.IGNORECASE)
stop = re.compile(r"停止|暂停|搁置|放弃|\bstop\b|\bpause\b|\bdefer\b|\babandon\b", re.IGNORECASE)
negative_prefix = re.compile(negative + r"\s*(?:再\s*)?$", re.IGNORECASE)

for clause in re.split(r"[，,。.;；！？!?\n]|\b(?:but|however)\b|但是|不过|但", text, flags=re.IGNORECASE):
    if not scope.search(clause):
        continue
    forbidden = negative_continuation.search(clause)
    if forbidden or any(not negative_prefix.search(clause[:m.start()]) for m in stop.finditer(clause)):
        print("不得停止或禁止继续可独立推进的工作", file=sys.stderr)
        sys.exit(1)
PY
if printf '%s' "$message" | grep -Eqi \
  '一个[^。.\n]*(等待|失败)[^。.\n]*(整体|全局)[^。.\n]*(阻塞|停止)|one[^.\n]*(wait|fail)[^.\n]*(overall|global)[^.\n]*(blocked|stop)'; then
  echo "单个等待或失败不得让整体目标提前阻塞" >&2
  exit 1
fi
