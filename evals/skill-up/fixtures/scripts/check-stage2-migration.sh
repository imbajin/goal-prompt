#!/usr/bin/env bash
# Legacy phrase checker for archived scores; current cases use semantic Judges.
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
    r"(?:不(?:应(?:该)?|要|得|能|会|可(?:以)?|必|再)?|不需要|不用|无需|禁止|严禁"
    r"|never|(?:do(?:es)?|did|must|should|will|would|could|can|is|are|was|were|need)\s+not"
    r"|(?:do(?:es)?|did|must|should|would|could|ca|wo|is|are|was|were)n['’]t|cannot|avoid|rather\s+than|instead\s+of)"
)
continuation = r"(?:继续|推进|执行|处理|continue|progress|proceed(?:\s+with)?|execute|work\s+on)"
negative_continuation = re.compile(negative + r"\s*(?:再\s*)?" + continuation, re.IGNORECASE)
stop = re.compile(r"停止|暂停|搁置|放弃|\bstop(?:s|ped|ping)?\b|\bpause(?:s|d|ing)?\b|\bdefer(?:s|red|ring)?\b|\babandon(?:s|ed|ing)?\b", re.IGNORECASE)
negative_prefix = re.compile(negative + r"\s*(?:(?:再|被)|(?:be|been|being)\b)?\s*$", re.IGNORECASE)
coordination = re.compile(
    r"\b(?:and|then|or|nor)\s+(?:(?:also|then)\s+)?(?=" + negative + r"|" + continuation + r"|" + stop.pattern + r")"
    r"|(?:并且?|而|然后)(?=" + negative + r"|" + continuation + r"|" + stop.pattern + r")"
    r"|\bwhile\s+(?=" + scope.pattern + r")"
    r"|(?:而|同时)(?=" + scope.pattern + r")",
    re.IGNORECASE,
)

for clause in re.split(r"[，,。.;；！？!?\n]|\b(?:but|however)\b|但是|不过|但", text, flags=re.IGNORECASE):
    # Coordinated actions can have different objects: defer the blocked item
    # AND continue independent work. Do not attach the first verb to both.
    actions = coordination.split(clause)
    for index, action_clause in enumerate(actions):
        subjects = list(scope.finditer(action_clause))
        if not subjects:
            # Coordinated verbs can share the following object's scope:
            # "do not continue AND proceed with independent work". Inherit
            # only for an objectless verb, never "do not continue blocked X".
            if (negative_continuation.search(action_clause)
                and re.search(negative + r"\s*" + continuation + r"\s*$", action_clause, re.IGNORECASE)
                and any(scope.search(later) for later in actions[index + 1:])):
                print("不得停止或禁止继续可独立推进的工作", file=sys.stderr)
                sys.exit(1)
            continue
        # A pre-nominal prohibition can qualify a different object:
        # "不处理生产数据的独立工作照常推进". Bind a preceding verb only
        # when the scope itself is its direct object; do not borrow modifiers.
        forbidden = any(
            subject.end() <= match.start()
            or (match.end() <= subject.start() and re.fullmatch(
                r"\s*(?:(?:the|any|all)\s+|(?:所有|任何|全部|这些))*", action_clause[match.end():subject.start()], re.IGNORECASE))
            for match in negative_continuation.finditer(action_clause)
            for subject in subjects
        )
        if forbidden or any(not negative_prefix.search(action_clause[:m.start()]) for m in stop.finditer(action_clause)):
            print("不得停止或禁止继续可独立推进的工作", file=sys.stderr)
            sys.exit(1)
PY
if printf '%s' "$message" | grep -Eqi \
  '一个[^。.\n]*(等待|失败)[^。.\n]*(整体|全局)[^。.\n]*(阻塞|停止)|one[^.\n]*(wait|fail)[^.\n]*(overall|global)[^.\n]*(blocked|stop)'; then
  echo "单个等待或失败不得让整体目标提前阻塞" >&2
  exit 1
fi
