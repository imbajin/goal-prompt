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
    fenced = re.search(r"```[^\n]*\n(/goal\b.*?)\n```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)

    direct = re.search(r"(?m)^/goal\b.*", text, re.DOTALL)
    if direct:
        return direct.group(0).rstrip()

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
