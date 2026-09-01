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
printf '%s' "$message" | grep -Eqi 'docs/requirement\.md'
printf '%s' "$message" | grep -Eqi 'docs/design\.md'
printf '%s' "$message" | grep -Eqi 'docs/todo\.md'
printf '%s' "$message" | grep -Eqi 'deep|深度|state\.md'
printf '%s' "$message" | grep -Eqi '恢复|recovery|重排|repriorit|independent work'
printf '%s' "$message" | grep -Eqi '3.*reviewer|three.*reviewer|三个.*reviewer'
