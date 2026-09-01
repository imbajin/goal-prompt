#!/usr/bin/env python3
"""Deterministically enforce the rendered /goal body character limit."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--limit", type=int, default=4000)
    return parser.parse_args()


def extract_goal(text: str) -> str:
    fence = re.compile(r"(?ms)^[ \t]*```[^\n]*\n(.*?)^[ \t]*```[ \t]*$")
    goal_line = re.compile(r"^[ \t]*/goal(?:[ \t]+(.*)|[ \t]*)$")
    if sum(bool(goal_line.match(line)) for line in text.splitlines()) != 1:
        raise ValueError("expected exactly one rendered /goal")
    for block in fence.finditer(text):
        lines = block.group(1).splitlines()
        for index, line in enumerate(lines):
            match = goal_line.match(line)
            if match:
                body = match.group(1) or ""
                if index + 1 < len(lines):
                    body = "\n".join((body, *lines[index + 1:]))
                return body.rstrip()

    lines = text.splitlines()
    for index, line in enumerate(lines):
        direct = goal_line.match(line)
        if direct:
            body_lines = [direct.group(1) or ""]
            for continuation in lines[index + 1:]:
                if re.match(
                    r"^[ \t]*(?:Explanation|Notes?|说明|备注)[ \t]*[:：]",
                    continuation,
                    re.IGNORECASE,
                ):
                    break
                body_lines.append(continuation)
            return "\n".join(body_lines).rstrip()

    raise ValueError("no rendered /goal found")


def main() -> int:
    args = parse_args()
    if args.limit <= 0:
        print("--limit must be positive", file=sys.stderr)
        return 2

    if args.source:
        text = args.source.read_text(encoding="utf-8")
        source = str(args.source)
    else:
        text = os.environ.get("EVAL_FINAL_MESSAGE", "")
        source = "EVAL_FINAL_MESSAGE"

    try:
        goal = extract_goal(text)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    if not goal.strip():
        print("rendered /goal body is empty", file=sys.stderr)
        return 1

    body = goal.removeprefix("/goal").lstrip()
    count = len(body)
    if count >= args.limit:
        print(
            f"FAIL goal body has {count} characters; must be below {args.limit} "
            f"(source: {source})",
            file=sys.stderr,
        )
        return 1

    print(
        f"PASS goal body has {count} characters; limit is below {args.limit} "
        f"(source: {source})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
