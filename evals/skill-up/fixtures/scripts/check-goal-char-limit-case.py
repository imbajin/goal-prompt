#!/usr/bin/env python3
"""Check the event-bus goal's length and retained completion contract."""

from __future__ import annotations

import os
import re
import sys


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
                return "\n".join((match.group(1) or "", *lines[index + 1 :])).rstrip()

    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = goal_line.match(line)
        if not match:
            continue
        body = [match.group(1) or ""]
        for continuation in lines[index + 1 :]:
            if re.match(
                r"^[ \t]*(?:Explanation|Notes?|说明|备注)[ \t]*[:：]",
                continuation,
                re.IGNORECASE,
            ):
                break
            body.append(continuation)
        return "\n".join(body).rstrip()
    raise ValueError("no rendered /goal found")


def main() -> int:
    try:
        goal = extract_goal(os.environ.get("EVAL_FINAL_MESSAGE", ""))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    if not goal.strip():
        print("rendered /goal body is empty", file=sys.stderr)
        return 1
    goal = goal.lstrip()
    if len(goal) >= 4000:
        print(f"goal body has {len(goal)} characters; must be below 4000", file=sys.stderr)
        return 1

    checks = {
        "four modules": r"payments.*ledger.*reconciliation.*reporting",
        "public contracts": r"(?:public|公开).{0,40}API.{0,80}webhook",
        "state entrypoint": r"state\.md",
        "module tests and performance": r"(?:单元测试|unit tests?).{0,160}(?:契约测试|contract tests?).{0,160}(?:性能|performance).{0,80}5%",
        "data consistency": r"(?:数据一致|data consistency)",
        "rehearsed rollback": r"(?:回滚|rollback).{0,80}(?:演练|rehears)",
        "twelve sub-gates": r"(?:12|十二).{0,30}(?:门槛|gates?)",
        "CI and security": r"CI.{0,80}(?:安全|security)",
        "five reviewers and re-review": r"(?:5|五).{0,40}(?:reviewer|评审|审查).{0,120}(?:复审|re-?review)",
        "migration and operations docs": r"(?:迁移文档|migration docs?).{0,100}(?:运维手册|operations? manual|runbook)",
        "four-stage rollout and rollback": r"(?:4|四).{0,30}(?:阶段|stages?).{0,120}(?:回退|rollback)",
    }
    missing = [
        label
        for label, pattern in checks.items()
        if not re.search(pattern, goal, re.IGNORECASE | re.DOTALL)
    ]
    if missing:
        print("goal body is missing: " + ", ".join(missing), file=sys.stderr)
        return 1

    print(f"PASS goal body has {len(goal)} characters and retains all required gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
