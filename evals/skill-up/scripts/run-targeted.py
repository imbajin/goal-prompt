#!/usr/bin/env python3
"""冻结并运行仅 with-Skill 的定向评测；不复制凭据或改写 HOME/CODEX_HOME。"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

INVOCATION_PREFIX = (
    "$goal-prompt\n"
    "请先读取当前工作区的 .codex/skills/goal-prompt/SKILL.md，再按其适用边界处理下方原始请求。"
    "如果原始请求明确是普通非目标工作，直接处理原任务，不生成目标文本。\n\n原始请求：\n"
)

DISABLED_FEATURES = (
    "apps", "plugins", "memories", "goals", "multi_agent", "multi_agent_v2",
    "skill_search", "hooks", "browser_use", "browser_use_external",
    "browser_use_full_cdp_access", "computer_use", "in_app_browser",
    "workspace_dependencies", "image_generation", "remote_plugin",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def captured(command: list[str]) -> str:
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()


def reject_skill_symlinks(skill: Path) -> None:
    """拒绝 Skill 树内所有符号链接，包括失效链接；不读取链接目标。"""
    if skill.is_symlink() or any(path.is_symlink() for path in skill.rglob("*")):
        raise ValueError("Skill 源码树不能包含符号链接；请提供独立的普通目录")


def copy_skill_tree(skill: Path, destination: Path) -> None:
    """复制前后检查，并保留复制中出现的链接以避免默认解引用。非 OS 隔离。"""
    reject_skill_symlinks(skill)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive ownership: never remove a pre-existing output on failure.
    destination.mkdir()
    try:
        shutil.copytree(skill, destination, symlinks=True, dirs_exist_ok=True)
        reject_skill_symlinks(skill)
        reject_skill_symlinks(destination)
    except BaseException:
        shutil.rmtree(destination)
        raise


def discover_host_skills() -> list[str]:
    roots = {Path.home() / ".codex/skills", Path.home() / ".agents/skills", Path("/etc/codex/skills")}
    if os.environ.get("CODEX_HOME"):
        roots.add(Path(os.environ["CODEX_HOME"]) / "skills")
    paths = set()
    for root in sorted(roots):
        visited = set()
        for current, dirs, files in os.walk(root, followlinks=True):
            resolved = Path(current).resolve()
            if resolved in visited:
                dirs[:] = []
                continue
            visited.add(resolved)
            if "SKILL.md" in files:
                paths.add(str((Path(current) / "SKILL.md").resolve()))
    return sorted(paths)


def make_wrapper(directory: Path, binary: str, host_paths: list[str]) -> dict:
    flags = ["--ignore-user-config", "--ignore-rules", "-c", "model_reasoning_effort=\"high\"",
             "-c", "web_search=\"disabled\"", "--enable", "skip_host_skill_discovery"]
    for feature in DISABLED_FEATURES:
        flags.extend(("--disable", feature))
    disabled = ",".join("{path=" + json.dumps(path) + ",enabled=false}" for path in host_paths)
    flags.extend(("-c", "skills.config=[" + disabled + "]"))
    wrapper = directory / "codex"
    wrapper.write_text("#!/usr/bin/env python3\nimport os, sys\n"
                       f"binary = {binary!r}\nflags = {flags!r}\n"
                       "args = sys.argv[1:]\n"
                       "if args and args[0] == 'exec':\n"
                       "    args = ['exec', *flags, *args[1:]]\n"
                       "os.execv(binary, [binary, *args])\n")
    wrapper.chmod(0o755)
    return {"binary": binary, "exec_flags": flags, "sha256": digest(wrapper)}


def skills_catalog(text: str) -> tuple[list[str], list[str]]:
    names, roots = [], []
    for block in re.findall(r"<skills_instructions>(.*?)</skills_instructions>", text, re.DOTALL):
        names.extend(re.findall(r"^\s*- ([\w][\w:-]*): ", block, re.MULTILINE))
        roots.extend(re.findall(r"^\s*- `r\d+` = `([^`]+)`", block, re.MULTILINE))
    return sorted(set(names)), sorted(set(roots))


def prompt_catalog(artifact: Path) -> tuple[list[str], list[str]]:
    texts = []
    for item in json.loads(artifact.read_text()):
        for block in item.get("content", []):
            if isinstance(block, dict):
                texts.append(block.get("text", ""))
    return skills_catalog("\n".join(texts))


def verify_catalog_evidence(output: Path, manifest: dict) -> None:
    if "catalog_preflight" not in manifest:
        raise ValueError("旧冻结记录缺少 catalog 隔离证明；仅可归档，必须重新冻结后执行")
    catalog = manifest["catalog_preflight"]
    artifact = output / "catalog-prompt-input.json"
    if not artifact.is_file() or digest(artifact) != catalog.get("prompt_input_sha256"):
        raise ValueError("冻结 catalog 证据不存在或哈希不匹配")
    names, roots = prompt_catalog(artifact)
    expected_root = str((output / "catalog-probe/.codex/skills").resolve())
    actual_roots = [str(Path(root).resolve()) for root in roots]
    recorded_roots = [str(Path(root).resolve()) for root in catalog.get("skill_roots", [])]
    if (catalog.get("model_called") is not False or names != ["goal-prompt"]
            or catalog.get("available_skill_names") != names
            or actual_roots != [expected_root] or recorded_roots != actual_roots):
        raise ValueError("冻结 catalog 元数据与证据不符，或未隔离到 workspace target")


def catalog_preflight(output: Path, binary: str, flags: list[str], skill: Path) -> dict:
    workspace = output / "catalog-probe"
    copy_skill_tree(skill, workspace / ".codex/skills/goal-prompt")
    debug_flags = [flag for flag in flags if flag not in ("--ignore-user-config", "--ignore-rules")]
    command = [binary, *debug_flags, "debug", "prompt-input", "检查本地目标 Skill 元数据。"]
    result = subprocess.run(command, cwd=workspace, capture_output=True, text=True)
    artifact = output / "catalog-prompt-input.json"
    artifact.write_text(result.stdout)
    (output / "catalog-preflight.stderr.log").write_text(result.stderr)
    if result.returncode:
        raise ValueError("Codex catalog 静态预检失败；尚未派发模型")
    names, roots = prompt_catalog(artifact)
    expected = str((workspace / ".codex/skills").resolve())
    if names != ["goal-prompt"] or [str(Path(root).resolve()) for root in roots] != [expected]:
        raise ValueError(f"catalog 未隔离到 workspace target：names={names}, roots={roots}；尚未派发模型")
    return {"available_skill_names": names, "skill_roots": roots,
            "prompt_input_sha256": digest(artifact), "model_called": False}


def audit_outputs(output: Path) -> None:
    audits = []
    for transcript in sorted(output.rglob("stdout.json")):
        reads = []
        commands = []
        for line in transcript.read_text(errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item", {})
            if event.get("type") != "item.completed" or not item.get("command"):
                continue
            command = item["command"]
            commands.append(command)
            if ("SKILL.md" in command or "references/" in command) and item.get("exit_code") == 0:
                content = item.get("aggregated_output", "")
                reads.append({"command": command, "output_characters": len(content),
                              "output_utf8_bytes": len(content.encode()),
                              "output_sha256": hashlib.sha256(content.encode()).hexdigest()})
        host_reads = [c for c in commands if re.search(
            r"(?:/Users/[^/]+/\.(?:agents|codex)/skills|/Users/[^/]+/github/goal-prompt|/memories/)", c)]
        observed = []
        catalog_names, catalog_roots = set(), set()
        for rollout in transcript.parent.glob("rollout-*.jsonl"):
            for line in rollout.read_text(errors="replace").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "response_item":
                    payload = event.get("payload", {})
                    if payload.get("role") == "developer":
                        text = "\n".join(block.get("text", "") for block in payload.get("content", []) if isinstance(block, dict))
                        names, roots = skills_catalog(text)
                        catalog_names.update(names)
                        catalog_roots.update(roots)
                if event.get("type") == "turn_context":
                    payload = event.get("payload", {})
                    value = {k: payload.get(k) for k in ("model", "effort", "cwd", "approval_policy", "sandbox_policy")}
                    if value not in observed:
                        observed.append(value)
        audits.append({
            "artifact": str(transcript.relative_to(output)), "successful_skill_read_commands": reads,
            "reference_names_mentioned_in_commands": sorted(set(re.findall(r"references/[\w./-]+", "\n".join(r["command"] for r in reads)))),
            "host_target_or_memory_read_candidates": host_reads, "observed_turn_context": observed,
            "available_skill_names": sorted(catalog_names), "catalog_skill_roots": sorted(catalog_roots),
            "note": "成功命令及输出长度仅为审计线索；需结合 transcript 确认实际读取。重复读取累计与初始 context 不同；非 OS 隔离证明。",
        })
    write_json(output / "transcript-audit.json", audits)


def run_frozen(output: Path, skill_up: Path, manifest: dict) -> int:
    # Recheck prepared payloads before hashing: identical-byte and dangling
    # links are otherwise invisible to the file/hash map.
    reject_skill_symlinks(output / "snapshot")
    verify_catalog_evidence(output, manifest)
    if "execution_started_utc" in manifest or "completed_utc" in manifest or (output / "reports").exists() or (output / "events.jsonl").exists():
        raise ValueError("冻结运行已经执行或留有部分证据；请新建输出目录，不得覆盖")
    if manifest.get("host_skill_paths_disabled") is not None and discover_host_skills() != manifest["host_skill_paths_disabled"]:
        raise ValueError("宿主 Skill 目录清单已变化；需重新冻结并核查 catalog")
    snapshot = output / "snapshot"
    actual = {str(p.relative_to(snapshot)): digest(p) for p in sorted(snapshot.rglob("*")) if p.is_file()}
    if actual != manifest["snapshot_sha256"]:
        raise ValueError("冻结 snapshot 哈希不匹配")
    if digest(output / "bin/codex") != manifest["wrapper"]["sha256"]:
        raise ValueError("冻结 wrapper 哈希不匹配")
    if digest(skill_up) != manifest["skill_up_sha256"]:
        raise ValueError("skill-up 二进制与冻结记录不匹配")
    if manifest.get("codex_binary_sha256") and digest(Path(manifest["codex_binary"])) != manifest["codex_binary_sha256"]:
        raise ValueError("Codex 启动文件哈希与冻结记录不匹配")
    if captured([manifest["codex_binary"], "--version"]) != manifest["codex"]:
        raise ValueError("Codex 版本与冻结记录不匹配")
    env = os.environ.copy()
    env["PATH"] = str(output / "bin") + os.pathsep + env["PATH"]
    env.pop("CODEX_THREAD_ID", None)
    env.pop("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", None)
    command = [str(skill_up), "run", str(snapshot / "evals/eval.yaml"), "--output-dir", str(output / "reports"),
               "--event-log", str(output / "events.jsonl"), "--no-delete"]
    write_json(output / "command.json", command)
    manifest["execution_started_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    write_json(output / "manifest.json", manifest)
    print(f"启动真实定向运行：{', '.join(manifest['cases'])}；证据 {output}", flush=True)
    with (output / "run.log").open("w") as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    manifest["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest["exit_code"] = result.returncode
    write_json(output / "manifest.json", manifest)
    audit_outputs(output)
    print(f"运行结束 exit={result.returncode}；证据 {output}", flush=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, help="源仓库根目录；运行归档脚本时显式传入")
    parser.add_argument("--skill", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--skill-up", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--invoke-skill", action="store_true", help="给首个用户回合加统一显式调用前缀，原始输入另存于 manifest")
    parser.add_argument("--run-prepared", action="store_true", help="校验并执行已有冻结 snapshot，拒绝覆盖执行证据")
    args = parser.parse_args()
    repo = (args.repo or Path(__file__).resolve().parents[3]).resolve()
    skill_up = (args.skill_up or repo / ".eval-work/bin/skill-up").resolve()
    output = args.output.resolve()
    if args.run_prepared:
        if args.prepare_only or args.skill or args.cases or args.invoke_skill:
            parser.error("--run-prepared 仅接受 --output、--repo 和 --skill-up")
        try:
            # Check before delegating to a historical archived runner, which
            # may predate the symlink policy.
            reject_skill_symlinks(output / "snapshot")
            manifest = json.loads((output / "manifest.json").read_text())
            verify_catalog_evidence(output, manifest)
            archived_runner = output / "run-targeted.py"
            if digest(archived_runner) != manifest["runner_sha256"]:
                raise ValueError("冻结 runner 哈希不匹配")
            if digest(Path(__file__)) != manifest["runner_sha256"]:
                print("当前入口与冻结 runner 不同；校验通过后使用归档 runner 执行。", flush=True)
                os.execv(sys.executable, [sys.executable, str(archived_runner), "--repo", str(repo),
                                         "--skill-up", str(skill_up), "--output", str(output), "--run-prepared"])
            return run_frozen(output, skill_up, manifest)
        except (OSError, ValueError, KeyError) as error:
            parser.error(str(error))
    if not args.skill or not args.cases:
        parser.error("冻结新运行需要 --skill 与 --cases")
    try:
        # Check the supplied root before resolve() hides a root symlink.
        reject_skill_symlinks(args.skill)
    except ValueError as error:
        parser.error(str(error))
    skill = args.skill.resolve()
    if output.exists():
        parser.error("输出目录必须不存在；不得覆盖冻结证据或复用旧运行产物")
    if not (skill / "SKILL.md").is_file():
        parser.error("--skill 必须指向包含 SKILL.md 的目录")
    # Only preparing eval configuration needs the optional PyYAML dependency.
    import yaml

    codex = shutil.which("codex")
    if not codex:
        parser.error("未安装 codex")
    if captured([str(skill_up), "--version"]) != "skill-up version 0.14.0":
        parser.error("本冻结协议要求 skill-up 0.14.0")
    output.mkdir(parents=True)
    shutil.copy2(Path(__file__), output / "run-targeted.py")
    snapshot = output / "snapshot"
    snapshot.mkdir()
    (snapshot / "evals").mkdir()
    copy_skill_tree(skill, snapshot / "target/goal-prompt")
    shutil.copy2(snapshot / "target/goal-prompt/SKILL.md", snapshot / "SKILL.md")
    shutil.copytree(repo / "evals/skill-up/cases", snapshot / "skill-up/cases")
    shutil.copytree(repo / "evals/skill-up/fixtures", snapshot / "skill-up/fixtures")
    config = yaml.safe_load((repo / "evals/skill-up/eval.yaml").read_text())
    selected = []
    inputs = {}
    for case in args.cases:
        path = snapshot / "skill-up/cases" / (case + ".yaml")
        if not path.is_file():
            parser.error(f"未知 case: {case}")
        original = yaml.safe_load(path.read_text())
        original_input = json.loads(json.dumps(original["input"]))
        if args.invoke_skill:
            shutil.copy2(path, snapshot / "skill-up/cases" / (case + ".original.yaml"))
            if "prompt" in original["input"]:
                original["input"]["prompt"] = INVOCATION_PREFIX + original["input"]["prompt"]
            else:
                for turn in original["input"].get("turns", []):
                    if turn.get("role") == "user":
                        turn["content"] = INVOCATION_PREFIX + turn["content"]
                        break
                else:
                    parser.error(f"case {case} 缺少可显式调用的用户回合")
            path.write_text(yaml.safe_dump(original, allow_unicode=True, sort_keys=False))
        inputs[case] = {"original": original_input, "dispatched": original["input"]}
        selected.append("skill-up/cases/" + path.name)
    config["skills"] = [{"source": "local_path", "path": "target/goal-prompt"}]
    config["engine"]["version"] = captured([codex, "--version"]).removeprefix("codex-cli ")
    config["cases"]["files"] = selected
    config["cases"]["parallelism"] = 1
    config["cases"]["defaults"]["collect_artifacts"] = [".goal-task/**/*.md"]
    config["benchmark"] = {"enabled": False}
    config_path = snapshot / "evals/eval.yaml"
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    wrapper_dir = output / "bin"
    wrapper_dir.mkdir()
    host_paths = discover_host_skills()
    wrapper = make_wrapper(wrapper_dir, codex, host_paths)
    catalog = catalog_preflight(output, codex, wrapper["exec_flags"], snapshot / "target/goal-prompt")
    env = os.environ.copy()
    env["PATH"] = str(wrapper_dir) + os.pathsep + env["PATH"]
    # 防止从当前父会话串入 thread ID；保留原登录环境，不读取凭据文件。
    env.pop("CODEX_THREAD_ID", None)
    env.pop("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", None)
    files = {str(p.relative_to(snapshot)): digest(p) for p in sorted(snapshot.rglob("*")) if p.is_file()}
    manifest = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python": sys.version, "pyyaml": yaml.__version__,
        "skill_up": captured([str(skill_up), "--version"]), "skill_up_sha256": digest(skill_up),
        "codex": captured([codex, "--version"]), "codex_binary": codex, "codex_binary_sha256": digest(Path(codex)),
        "login_status": captured([codex, "login", "status"]),
        "runner_sha256": digest(Path(__file__)), "engine": config["engine"], "judge": config.get("judge"),
        "reasoning_effort": "high", "cases": args.cases,
        "invocation_mode": "explicit" if args.invoke_skill else "natural",
        "invocation_prefix": INVOCATION_PREFIX if args.invoke_skill else None,
        "case_inputs": inputs, "host_skill_paths_disabled": host_paths, "catalog_preflight": catalog,
        "retry_policy": config["cases"]["retry_policy"], "defaults": config["cases"]["defaults"],
        "wrapper": wrapper, "snapshot_sha256": files,
        "isolation": "每 case 使用 skill-up 新工作区；沿用当前授权登录，HOME/CODEX_HOME 均未改写。显式禁用已发现宿主 Skill（含符号链接）并静态核查 catalog 仅含 workspace target；禁附加能力，实际运行另审计；非 OS hermetic。",
        "evidence_limit": "这是 prompt-level with-Skill 定向实测；不证明目标实际执行或 Claude Code 运行兼容。",
    }
    write_json(output / "manifest.json", manifest)
    for command, name in (([str(skill_up), "validate", str(config_path)], "validate"),
                          ([str(skill_up), "run", str(config_path), "--dry-run"], "dry-run")):
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        (output / (name + ".log")).write_text(result.stdout + result.stderr)
        if result.returncode:
            print(f"{name} 失败，证据：{output}", flush=True)
            return result.returncode
    if args.prepare_only:
        print(f"冻结完成（未调用模型）：{output}")
        return 0
    return run_frozen(output, skill_up, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
