#!/usr/bin/env python3
"""仅允许无 Skill 的 Luna xhigh 评测；不读取或输出认证文件。"""
import os
import sys

args = sys.argv[1:]
if not args:
    raise SystemExit("禁止交互式或未声明的 Codex 调用")
if args[0] not in ("exec", "debug") and args not in (["--version"], ["-V"], ["--help"], ["-h"], ["login", "status"]):
    raise SystemExit("仅允许评测 exec 与无模型 version/help/login-status/prompt-input 预检")
if args and args[0] in ("exec", "debug"):
    mode = args[0]
    if mode == "exec" and os.environ.get("BASELINE_CODEX_RUNNING"):
        raise SystemExit("禁止被测 Agent 派发嵌套模型调用")
    seen_model = False
    for i, arg in enumerate(args):
        if arg in ("-m", "--model"):
            if i + 1 >= len(args) or args[i + 1] != "gpt-6-luna":
                raise SystemExit("本评测只允许 gpt-6-luna")
            seen_model = True
        elif arg.startswith("--model="):
            if arg != "--model=gpt-6-luna":
                raise SystemExit("本评测只允许 gpt-6-luna")
            seen_model = True
    flags = ["--ignore-user-config", "--ignore-rules",
             "-c", 'model_reasoning_effort="xhigh"',
             "-c", 'web_search="disabled"',
             "-c", 'model_provider="baseline-gateway"',
             "-c", 'model_providers.baseline-gateway.name="baseline-gateway"',
             "-c", 'model_providers.baseline-gateway.base_url="' + os.environ["BASELINE_API_BASE_URL"] + '"',
             "-c", 'model_providers.baseline-gateway.wire_api="responses"',
             "-c", 'model_providers.baseline-gateway.requires_openai_auth=false',  "--enable", "skip_host_skill_discovery"]
    for feature in ("apps", "plugins", "memories", "goals", "multi_agent", "multi_agent_v2",
                    "skill_search", "hooks", "browser_use", "browser_use_external",
                    "browser_use_full_cdp_access", "computer_use", "in_app_browser",
                    "workspace_dependencies", "image_generation", "remote_plugin", "shell_snapshot", "enable_request_compression"):
        flags += ["--disable", feature]
    disabled = [{"path": f"/root/.codex/skills/.system/{name}/SKILL.md", "enabled": False}
                for name in ("openai-docs", "skill-creator", "skill-installer", "plan", "imagegen")]
    flags += ["-c", "skills.config=[" + ",".join(
        '{path="' + row["path"] + '",enabled=false}' for row in disabled) + "]"]
    flags += ["-c", 'model="gpt-6-luna"']
    if mode == "debug":
        if len(args) < 2 or args[1] != "prompt-input":
            raise SystemExit("只允许无模型 prompt-input 预检")
        flags = [f for f in flags if f not in ("--ignore-user-config", "--ignore-rules")]
        args = [*flags, *args]
    else:
        args = ["exec", *flags, *args[1:]]
        os.environ["BASELINE_CODEX_RUNNING"] = "1"
os.execv("/usr/local/bin/codex-upstream", ["/usr/local/bin/codex-upstream", *args])
