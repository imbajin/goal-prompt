#!/usr/bin/env bash
set -euo pipefail

message="${EVAL_FINAL_MESSAGE:-}"
python3 - <<'PY'
import os
import re
import sys

message = os.environ.get("EVAL_FINAL_MESSAGE", "")
token = re.compile(r"(?<![\w./-])/goal(?![\w./-])")
# An explicit refusal to render the command is a mention, not a final goal.
# Only exempt a bare command name; payloads and rendered command lines fail.
negative = re.compile(
    r"(?:"
    r"(?:不(?:会|再|应|要|能)?|未|没有|尚未|暂不|先不)"
    r"(?:直接)?(?:生成|输出|写|提供|给出|给|交付|执行)"
    r"(?:[ \t]*(?:最终|可复制的?|可执行的?|完整的?|任何|的))*"
    r"|(?:will\s+not|won't|do\s+not|don't|not|never|without)\s+"
    r"(?:generate|generating|render|rendering|output|outputting|emit|write|provide)"
    r"(?:\s+(?:a|the|any|final|executable|copyable))*"
    r")[ \t]*[`\"'“‘]*$",
    re.IGNORECASE,
)
# A short confirmation condition still describes when a command may be rendered;
# it is not a command payload. Keep this grammar bounded: arbitrary text after a
# negated mention must continue to fail, including comma-separated goal content.
confirmation_tail = re.compile(
    r"[ \t`\"'”’]*(?:[,，][ \t]*)?(?:"
    r"(?:等(?:待)?|待)(?:你|您|用户)(?:确认|决定|选择)"
    r"(?:后再(?:生成|输出|提供|给出))?"
    r"|(?:until|before)\s+(?:you|the\s+user)\s+(?:confirms?|decides?|chooses?)"
    r"(?:\s+(?:the|this)\s+(?:brief|scope|plan))?"
    r")[ \t`\"'”’]*",
    re.IGNORECASE,
)
for match in token.finditer(message):
    line = message[message.rfind("\n", 0, match.start()) + 1:match.start()]
    rendered = re.fullmatch(r"[ \t]*(?:>[ \t]*)?(?:[-*][ \t]+)?[`\"']*", line)
    prefix = re.split(r"[\n。；;！？!?]", message[:match.start()])[-1]
    suffix = re.split(r"[\n。.;；！？!?]", message[match.end():], maxsplit=1)[0]
    bare = re.fullmatch(r"[ \t`\"'”’]*", suffix) or confirmation_tail.fullmatch(suffix)
    if rendered or not (bare and negative.search(prefix)):
        print("premature final goal", file=sys.stderr)
        sys.exit(1)
PY
# Accept semantic confirmation requests, not one fixed verb: a brief may ask
# the user to decide, choose, or provide the missing authorization.
printf '%s' "$message" | grep -Eqi '确认|决定|选择|需要你|请你|是否|confirm|decide|choose|please (confirm|decide|choose)'
printf '%s' "$message" | grep -Eqi '范围|scope'
printf '%s' "$message" | grep -Eqi '证据|evidence|验证|validation'
