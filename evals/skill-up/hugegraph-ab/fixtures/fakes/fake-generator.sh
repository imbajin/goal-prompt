#!/usr/bin/env bash
set -euo pipefail
[[ "${AB_FAKE_MODE:-}" == "1" ]] || { echo "fake generator requires AB_FAKE_MODE=1" >&2; exit 1; }
[[ $# -eq 2 ]] || { echo "usage: fake-generator.sh request workspace" >&2; exit 2; }
request="$1"
workspace="$2"
[[ -s "$request" && -d "$workspace" && -d "$workspace/version-evidence" ]] || exit 1
printf '/goal fake-prompt skill=%s request-bytes=%s\n' \
  "${AB_SKILL_MODE:?}" "$(wc -c <"$request" | tr -d ' ')"
