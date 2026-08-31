#!/usr/bin/env python3
"""Deterministically check that a generated goal names required execution gates.

This is intentionally a structural gate, not a quality or correctness judge. It
checks that the output makes the relevant contract visible; the execution goal
and its normal tests still need separate semantic and runtime verification.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def read_source(args: argparse.Namespace) -> tuple[str, str]:
    if args.root and args.source:
        raise SystemExit("choose --root, --source, or EVAL_FINAL_MESSAGE, not more than one")

    if args.root:
        root = args.root.expanduser().resolve()
        if not root.is_dir():
            raise SystemExit(f"artifact root does not exist: {root}")
        state_files = sorted(path for path in root.rglob("*.md") if path.name == "state.md")
        if len(state_files) != 1:
            raise SystemExit(f"artifact root must contain exactly one state.md: {root}")
        state = state_files[0]
        return state.read_text(), str(state)

    if args.source:
        path = args.source.expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"source file does not exist: {path}")
        return path.read_text(), str(path)

    message = os.environ.get("EVAL_FINAL_MESSAGE", "")
    if not message.strip():
        raise SystemExit("EVAL_FINAL_MESSAGE is empty and no --source/--root was supplied")
    return message, "EVAL_FINAL_MESSAGE"


def has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def negated_requirements(profile: str, text: str) -> list[str]:
    """Reject explicit negation of a contract gate, not ordinary caveats."""
    if profile == "parallel":
        checks = [
            (
                "single owner for shared schema or lockfile",
                r"(?:schema|lockfile|共享).{0,120}(?:multiple|several|two|多个|多名|两个|共同|联合|co-owned|jointly owned).{0,80}(?:owners?|writers?|负责人|写入者|agent)|(?:multiple|several|two|多个|多名|两个).{0,80}(?:owners?|writers?|负责人|写入者|agent).{0,120}(?:schema|lockfile|共享)|(?:schema|lockfile|共享).{0,120}(?:may also|can also|也可|也能|也可以).{0,80}(?:modify|edit|write|修改|编辑|写入)|(?:any agent|任意 agent|任何 agent).{0,80}(?:modify|edit|write|修改|编辑|写入).{0,120}(?:schema|lockfile|共享)|(?:schema|lockfile|共享).{0,120}(?:advisory only|仅供参考|非强制)|(?:schema|lockfile|共享).{0,120}(?:writable|editable|modifiable|可写|可编辑|可修改).{0,60}(?:by\s+)?(?:all|every|any)\s+(?:agents?|workers?)|(?:schema|lockfile|共享).{0,120}(?:but|except|however|但|不过|除外).{0,80}(?:auth|billing|notifications|another agent|other agent|all agents|every agent|everyone|other workers?|non-owners?|另一个 agent|其他 agent|所有 agent|全部 agent|每个 agent|非 owner).{0,80}(?:may|can)\s+(?:modify|edit|write)|(?:another agent|other agent|all agents|every agent|everyone|other workers?|non-owners?|另一个 agent|其他 agent|所有 agent|全部 agent|每个 agent|非 owner).{0,80}(?:may|can)\s+(?:modify|edit|write).{0,80}(?:it|schema|lockfile|共享)|(?:another agent|other agent|all agents|every agent|everyone|other workers?|non-owners?|另一个 agent|其他 agent|所有 agent|全部 agent|每个 agent|非 owner).{0,80}(?:allowed|permitted|authorized|(?:has|have) permission|允许|获准|授权).{0,80}(?:modify|edit|write|修改|编辑|写入)",
            ),
        ]
        return [label for label, pattern in checks if has(text, pattern)]

    if profile == "ui":
        checks = [
            (
                "Chrome browser_use",
                r"(?:不要|不应|无需|不需要|禁止|跳过|省略|绕过).{0,80}(?:使用|运行)?.{0,80}(?:chrome|browser[_ -]?use)|(?:chrome|browser[_ -]?use).{0,80}(?:可选|非必需|不是必须|无需|不需要|跳过|省略|绕过|建议而非硬性门槛|不是硬性门槛|非硬性门槛|非强制门槛|可不执行|仅为建议|只是建议|仅作建议|只是指导|推荐做法|不是硬性要求|非强制要求|不是验收门槛|optional|not required|not mandatory|not a (?:hard|required|mandatory) gate|may\s+be\s+(?:skipped|omitted|bypassed)|can\s+be\s+(?:skipped|omitted|bypassed)|suggestion rather than a gate|guidance rather than a gate|non-binding|merely a suggestion)|(?:skip|omit|bypass).{0,80}(?:chrome|browser[_ -]?use)|do not.{0,80}(?:use|run).{0,80}(?:chrome|browser[_ -]?use)",
            ),
        ]
        return [label for label, pattern in checks if has(text, pattern)]

    if profile != "long":
        return []
    checks = [
        (
            "milestone commit",
            r"(?:(?:do\s+not|don't|不要)(?!.{0,20}(?:skip|omit|forget|fail\s+to|leave\s+without|avoid|避免|跳过|省略|遗漏|忘记|未能)).{0,60}|(?:(?:\bno\b|(?<!leave\s)\bwithout\b|没有)(?!\s*(?:skip|skipping|omit|omitting|跳过|省略|遗漏))|无需|不需要|禁止|不得).{0,60})(?:milestone|里程碑).{0,40}(?:commit|提交)|(?:do\s+not|don't|不要).{0,20}(?:forget|忘记).{0,20}(?:avoid|避免).{0,20}(?:create|creating|make|making|add|adding|创建|生成).{0,30}(?:milestone|里程碑).{0,40}(?:commit|提交)|(?:do\s+not|don't|不要)(?!\s*.{0,20}(?:forget|忘记|fail\s+to|未能)).{0,20}(?:avoid|避免)\s+(?:skip|skipping|omit|omitting|跳过|省略|遗漏).{0,40}(?:milestone|里程碑).{0,40}(?:commit|提交)|(?:milestone|里程碑).{0,40}(?:commit|提交).{0,60}(?:not\s+(?:required|mandatory|needed)|unnecessary|optional|不是必须|不是必需|非必需|非必要|不必|不用|无需|不需要|可选)",
        ),
        (
            "state checkpoint",
            r"(?:(?:do\s+not|don't|不要)(?!.{0,20}(?:skip|omit|forget|fail\s+to|leave\s+without|avoid|避免|跳过|省略|遗漏|忘记|未能)).{0,80}|(?:(?:\bno\b|(?<!leave\s)\bwithout\b|没有)(?!\s*(?:skip|skipping|omit|omitting|跳过|省略|遗漏))|无需|不需要|禁止|不得).{0,80})(?:persist|save|write|写入|保存|记录).{0,40}(?:state\.md|状态文件)|(?:do\s+not|don't|不要).{0,20}(?:forget|忘记).{0,20}(?:avoid|避免).{0,20}(?:write|save|persist|写入|保存|记录).{0,40}(?:state\.md|状态文件)|(?:do\s+not|don't|不要)(?!\s*.{0,20}(?:forget|忘记|fail\s+to|未能)).{0,20}(?:avoid|避免)\s+(?:skip|skipping|omit|omitting|跳过|省略|遗漏).{0,40}(?:state\.md|状态文件).{0,40}(?:checkpoint|检查点|状态记录)|(?:(?:\bno\b|(?<!leave\s)\bwithout\b|没有)(?!\s*(?:skip|skipping|omit|omitting|跳过|省略|遗漏))|不存在|(?:不要)(?!.{0,20}(?:skip|omit|forget|fail\s+to|leave\s+without|avoid|避免|跳过|省略|遗漏|忘记|未能))).{0,40}(?:state\.md|状态文件).{0,40}(?:checkpoint|检查点|状态记录)|(?:state\.md|状态文件|状态记录).{0,60}(?:checkpoint|检查点|状态记录).{0,60}(?:not\s+(?:required|mandatory|needed)|unnecessary|optional|不是必须|不是必需|非必需|非必要|不必|不用|无需|不需要|可选)",
        ),
        (
            "independent reviewer",
            r"(?:(?:do\s+not|don't|不要)(?!.{0,20}(?:skip|omit|forget|fail\s+to|leave\s+without|avoid|避免|跳过|省略|遗漏|忘记|未能)).{0,60}|(?:(?:\bno\b|(?<!leave\s)\bwithout\b|没有)(?!\s*(?:skip|skipping|omit|omitting|跳过|省略|遗漏))|无需|不需要|禁止|不得).{0,60})(?:independent reviewer|独立(?:的)?(?:reviewer|审查|评审))|(?:do\s+not|don't|不要).{0,20}(?:forget|忘记).{0,20}(?:avoid|避免).{0,20}(?:independent reviewer|独立(?:的)?(?:reviewer|审查|评审))|(?:do\s+not|don't|不要)(?!\s*.{0,20}(?:forget|忘记|fail\s+to|未能)).{0,20}(?:avoid|避免)\s+(?:skip|skipping|omit|omitting|跳过|省略|遗漏).{0,40}(?:independent reviewer|独立(?:的)?(?:reviewer|审查|评审))|(?:independent reviewer|独立(?:的)?(?:reviewer|审查|评审)).{0,60}(?:not\s+(?:required|mandatory|needed)|unnecessary|optional|不是必须|不是必需|非必需|非必要|不必|不用|无需|不需要|可选)",
        ),
    ]
    return [label for label, pattern in checks if has(text, pattern)]


def checks_for(profile: str) -> list[tuple[str, tuple[str, ...]]]:
    if profile == "long":
        return [
            (
                "progress bar and gate-based percentage",
                (
                    r"progress\s*\[[^\n\]]*\]\s*\d+%",
                    r"进度条.{0,100}\d+%",
                    r"进度.{0,100}\d+%.{0,40}(?:\d+\s*/\s*\d+|gates?/总|estimate|估计|粗粒度)",
                    r"进度.{0,100}(百分比|百分数|gates?/总)",
                ),
            ),
            (
                "milestone commit",
                (
                    r"(?:milestone|里程碑).{0,160}(?:commit|提交)",
                    r"(?:commit|提交).{0,160}(?:milestone|里程碑)",
                ),
            ),
            (
                "current completed-item summary",
                (
                    r"(?:current|当前|本轮).{0,100}(?:completed|完成).{0,100}(?:item|事项|内容|工作|项)",
                    r"(?:completed|完成).{0,100}(?:item|事项|内容|工作|项).{0,100}(?:summary|摘要|总结)",
                    r"完成事项|当前完成内容|本轮完成内容",
                    r"已创建并验证",
                ),
            ),
            (
                "compaction or handoff checkpoint in state.md",
                (
                    r"(?:compaction|压缩|quota|配额|handoff|交接).{0,180}(?:state\.md|状态文件|状态记录)",
                    r"(?:state\.md|状态文件|状态记录).{0,180}(?:compaction|压缩|quota|配额|handoff|交接)",
                ),
            ),
            (
                "remaining work and next action",
                (
                    r"remaining.{0,100}next",
                    r"剩余.{0,100}(下一步|下步)",
                    r"下一步.{0,100}剩余",
                ),
            ),
        ]

    if profile == "parallel":
        return [
            (
                "parallel work and independent lanes",
                (
                    r"parallel.{0,120}(?:agent|worker|lane)",
                    r"(?:agent|worker|lane).{0,120}parallel",
                    r"并行.{0,120}(?:agent|子 agent|worker|任务)",
                ),
            ),
            (
                "non-overlapping ownership",
                (
                    r"(?:ownership|owner|file boundaries|所有权|文件边界|归属)",
                ),
            ),
            (
                "single owner for shared schema or lockfile",
                (
                    r"(?:schema|lockfile|共享).{0,180}(?:single owner|唯一 owner|唯一归属|独占|唯一负责人)",
                    r"(?:single owner|唯一 owner|唯一归属|独占|唯一负责人).{0,180}(?:schema|lockfile|共享)",
                ),
            ),
            (
                "integration seam and post-integration rerun",
                (
                    r"(?:integrat|接缝).{0,180}(?:re-?run|rerun|复跑|复验|重跑|重新运行|再次运行|再次验证)",
                    r"(?:re-?run|rerun|复跑|复验|重跑|重新运行|再次运行|再次验证).{0,180}(?:integrat|接缝)",
                ),
            ),
            (
                "independent reviewer",
                (
                    r"independent reviewer",
                    r"独立.{0,80}(?:reviewer|审查|评审)",
                ),
            ),
        ]

    if profile == "ui":
        return [
            (
                "Chrome browser_use",
                (r"chrome.{0,100}browser[_ -]?use", r"browser[_ -]?use.{0,100}chrome"),
            ),
            (
                "real success and failure interaction",
                (
                    r"(?:success|成功).{0,160}(?:failure|失败|error|错误)",
                    r"(?:failure|失败|error|错误).{0,160}(?:success|成功)",
                ),
            ),
            (
                "browser screenshots or evidence",
                (r"(?:screenshot|截图|浏览器截图).{0,120}(?:browser|chrome|成功|失败)?", r"browser evidence", r"浏览器证据"),
            ),
            (
                "separate UI/UX and accessibility checks",
                (r"ui/?ux.{0,120}accessib", r"accessib.{0,120}ui/?ux", r"UI/UX",),
            ),
            (
                "static checks cannot replace browser acceptance",
                (
                    r"(?:build|构建|dom|静态).{0,120}(?:not|不能|不得|cannot).{0,120}(?:replace|代替|替代)",
                    r"(?:not|不能|不得|cannot).{0,120}(?:replace|代替|替代).{0,120}(?:build|构建|dom|静态)",
                    r"不能以.{0,120}(?:构建|单元测试|DOM|静态).{0,120}替代",
                    r"不得把.{0,120}(?:构建|单元测试|DOM|静态).{0,120}(?:作为|当作).{0,80}(?:验收|证据)",
                ),
            ),
        ]

    raise SystemExit(f"unknown profile: {profile!r}; expected long, parallel, or ui")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=("long", "parallel", "ui"))
    parser.add_argument("--source", type=Path, help="read one generated Markdown/text file")
    parser.add_argument("--root", type=Path, help="scan all generated Markdown files below this directory")
    args = parser.parse_args()

    text, source = read_source(args)
    negated = negated_requirements(args.profile, text)
    if negated:
        print(f"FAIL goal contract ({args.profile}; source: {source})", file=sys.stderr)
        for label in negated:
            print(f"- explicitly negated: {label}", file=sys.stderr)
        return 1
    missing = [label for label, patterns in checks_for(args.profile) if not has(text, *patterns)]
    if missing:
        print(f"FAIL goal contract ({args.profile}; source: {source})", file=sys.stderr)
        for label in missing:
            print(f"- missing: {label}", file=sys.stderr)
        return 1

    print(f"PASS goal contract ({args.profile}; source: {source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
