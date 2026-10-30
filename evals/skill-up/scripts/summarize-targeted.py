#!/usr/bin/env python3
"""归档定向实测的小体积证据；显式脚本 replay 不覆盖原始模型结果。"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

MAX_BYTES = 2 * 1024 * 1024
SECRET = re.compile(rb"(?:sk-(?:ant-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def reject_snapshot_symlinks(snapshot: Path) -> None:
    """拒绝快照中的所有链接，不能把同字节或失效链接当作已核实文件。"""
    if snapshot.is_symlink() or any(path.is_symlink() for path in snapshot.rglob("*")):
        raise ValueError("冻结 snapshot 不能包含符号链接")


def archive(source: Path, destination: Path, output: Path, run: Path) -> dict:
    source = source.resolve()
    if not source.is_relative_to(run):
        raise ValueError(f"证据路径越出运行目录：{source}")
    if not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise ValueError(f"证据不存在或超过 {MAX_BYTES} 字节：{source}")
    data = source.read_bytes()
    if SECRET.search(data):
        raise ValueError(f"证据疑似含凭据，拒绝公开归档：{source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return {"original_path": str(source), "archive": str(destination.relative_to(output)),
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def replay(script: Path, response: str, case_dir: Path, target: Path, output: Path) -> dict:
    if not script.is_file() or script.suffix not in (".sh", ".py"):
        raise ValueError(f"replay 仅支持显式 shell/python 判分脚本：{script}")
    # 无模型调用；仅给当前判分器重放冻结输出，不修改原结果。
    env = os.environ.copy()
    env["EVAL_FINAL_MESSAGE"] = response
    env["EVAL_WORKSPACE"] = str(case_dir / "outputs/workspace")
    env["EVAL_TRANSCRIPT_PATH"] = str(case_dir / "outputs/agent/run/stdout.json")
    command = ["bash" if script.suffix == ".sh" else sys.executable, str(script)]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
    value = {"kind": "deterministic_script_replay_not_model_rerun", "script_path": str(script),
             "script_sha256": sha256(script), "command": command, "exit_code": result.returncode,
             "stdout": result.stdout, "stderr": result.stderr,
             "verdict": "PASS" if result.returncode == 0 else "FAIL",
             "response_sha256": hashlib.sha256(response.encode()).hexdigest(),
             "original_verdict_unchanged": True}
    if SECRET.search(json.dumps(value).encode()):
        raise ValueError(f"replay 输出疑似含凭据，拒绝归档：{script}")
    write_json(target, value)
    return {**value, "artifact": str(target.relative_to(output))}


def case_artifacts(case_dir: Path, target: Path, output: Path, run: Path) -> list[dict]:
    """白名单包含尚无 cohort result 的 partial case，不扫描 rollout。"""
    evidence = []
    for relative in ("grading.json", "evaluation.json", "outputs/response.md"):
        source = case_dir / relative
        if source.is_file():
            evidence.append(archive(source, target / relative, output, run))
    for source in sorted((case_dir / "outputs/workspace/.goal-task").rglob("*.md")):
        evidence.append(archive(source, target / source.relative_to(case_dir), output, run))
    metadata = case_dir.parent / "eval_metadata.json"
    if metadata.is_file():
        evidence.append(archive(metadata, target.parent / metadata.name, output, run))
    return evidence


def case_events(run: Path) -> tuple[dict, dict]:
    """读取事件日志的当前快照，只保留每个 case 的开始/完成事件。"""
    path = run / "events.jsonl"
    events = {}
    observed = {"original_path": str(path), "observed_bytes": 0}
    hasher = hashlib.sha256()
    if not path.is_file():
        return events, observed
    with path.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            hasher.update(raw)
            observed["observed_bytes"] += len(raw)
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                # 活跃写入仅允许最后一行尚未写完整，不忽略中间损坏。
                if not raw.endswith(b"\n"):
                    observed["incomplete_trailing_line"] = number
                    break
                raise ValueError(f"事件日志 JSON 损坏：{path}:{number}")
            if event.get("event") not in ("case_started", "case_completed"):
                continue
            payload = event.get("payload", {})
            case_id = payload.get("case_id", "")
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", case_id):
                raise ValueError(f"事件 case ID 非法：{path}:{number}")
            if payload.get("configuration") != "with_skill":
                raise ValueError("本报告仅接受 with-Skill 定向 cohort 事件")
            key = (case_id, f"iteration-{int(payload['iteration'])}")
            if event["event"] == "case_completed" and payload.get("status") not in ("PASS", "FAIL", "ERROR", "SKIP"):
                raise ValueError(f"未知事件 status：{path}:{number}")
            events[key] = {"event": event, "original_path": str(path), "line_number": number,
                           "line_sha256": hashlib.sha256(raw).hexdigest()}
    observed["observed_sha256"] = hasher.hexdigest()
    return events, observed


def summarize_run(run: Path, output: Path, replay_scripts: dict[str, Path]) -> dict:
    reject_snapshot_symlinks(run / "snapshot")
    manifest = json.loads((run / "manifest.json").read_text())
    target = output / run.name
    target.mkdir()
    copied = []
    for relative in ("manifest.json", "command.json", "snapshot/evals/eval.yaml", "transcript-audit.json"):
        source = run / relative
        if source.is_file():
            copied.append(archive(source, target / relative, output, run))
    mismatches = []
    for relative, expected in manifest.get("snapshot_sha256", {}).items():
        source = run / "snapshot" / relative
        if not source.is_file() or sha256(source) != expected:
            mismatches.append(relative)
    if mismatches:
        raise ValueError(f"冻结快照哈希不匹配：{run}: {mismatches}")
    result_paths = sorted((run / "reports").glob("iteration-*/result.json"))
    info = {"run": run.name, "original_directory": str(run),
            "state": "completed" if "completed_utc" in manifest else "pending",
            "created_utc": manifest.get("created_utc"), "completed_utc": manifest.get("completed_utc"),
            "exit_code": manifest.get("exit_code"), "skill_up": manifest.get("skill_up"),
            "codex": manifest.get("codex"), "engine": manifest.get("engine"), "judge": manifest.get("judge"),
            "reasoning_effort": manifest.get("reasoning_effort"),
            "invocation_mode": manifest.get("invocation_mode"),
            "invocation_prefix": manifest.get("invocation_prefix"),
            "snapshot_verified": True, "isolation": manifest.get("isolation"),
            "evidence_limit": manifest.get("evidence_limit"), "artifacts": copied, "cases": []}
    events, event_observation = case_events(run)
    info["event_log_observation"] = event_observation
    seen = set()
    for result_path in result_paths:
        result = json.loads(result_path.read_text())
        if "case_results" not in result:
            raise ValueError(f"无法识别 result schema：{result_path}")
        copied.append(archive(result_path, target / result_path.relative_to(run), output, run))
        for case in result["case_results"]:
            case_id = case["case_id"]
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", case_id):
                raise ValueError(f"不安全的 case ID：{case_id!r}")
            variant = case.get("configuration", "with_skill")
            if variant != "with_skill":
                raise ValueError("本报告仅接受 with-Skill 定向 cohort")
            seen.add((case_id, result_path.parent.name))
            case_dir = result_path.parent / case_id / variant
            case_target = target / case_dir.relative_to(run)
            evidence = case_artifacts(case_dir, case_target, output, run)
            status = case.get("status")
            if status not in ("PASS", "FAIL", "ERROR", "SKIP"):
                raise ValueError(f"未知 case status：{status!r}")
            entry = {"case_id": case_id, "iteration": result_path.parent.name,
                     "status": status, "status_source": str(result_path) + "#case_results/" + case_id + "/status",
                     "duration_ms": case.get("duration_ms"), "turns": case.get("turns"),
                     "input_tokens": case.get("input_tokens"), "output_tokens": case.get("output_tokens"),
                     "judge_input_tokens": case.get("judge_input_tokens", 0),
                     "judge_output_tokens": case.get("judge_output_tokens", 0),
                     "gates": case.get("gates"), "grading": case.get("grading"),
                     "judge_results": case.get("judge_results"), "error": case.get("error"),
                     "artifacts": evidence}
            if case_id in replay_scripts:
                response_path = case_dir / "outputs/response.md"
                response = response_path.read_text() if response_path.is_file() else case.get("response", "")
                case_target.mkdir(parents=True, exist_ok=True)
                entry["current_script_replay"] = replay(replay_scripts[case_id], response, case_dir,
                                                        case_target / "current-script-replay.json", output)
            info["cases"].append(entry)
    for (case_id, iteration), source in events.items():
        if (case_id, iteration) in seen:
            continue  # 最终 result 优先；事件只补充尚未落盘的 case。
        event = source["event"]
        payload = event["payload"]
        case_dir = run / "reports" / iteration / case_id / "with_skill"
        case_target = target / case_dir.relative_to(run)
        evidence = case_artifacts(case_dir, case_target, output, run)
        completed = event["event"] == "case_completed"
        status = payload["status"] if completed else "RUNNING"
        case_target.mkdir(parents=True, exist_ok=True)
        event_artifact = case_target / "case-status-event.json"
        if SECRET.search(json.dumps(source).encode()):
            raise ValueError(f"状态事件疑似含凭据：{run}:{case_id}")
        write_json(event_artifact, source)
        grading_path = case_dir / "grading.json"
        entry = {"case_id": case_id, "iteration": iteration, "status": status,
                 "status_source": str(run / "events.jsonl") + f":{source['line_number']}#payload/status" if completed else str(run / "events.jsonl") + f":{source['line_number']}#case_started",
                 "execution_state": "completed_case_cohort_pending" if completed else "dispatched_incomplete",
                 "reason": "cohort result 尚未落盘；case 状态取自完成事件" if completed else "已派发，尚无 case_completed 或最终 result；不计为通过",
                 "status_event_artifact": str(event_artifact.relative_to(output)),
                 "duration_ms": payload.get("duration_ms"),
                 "grading": json.loads(grading_path.read_text()) if grading_path.is_file() else None,
                 "artifacts": evidence}
        # 即使 partial grading 已有全分，也不能将 RUNNING 升为 PASS。
        response_path = case_dir / "outputs/response.md"
        if completed and case_id in replay_scripts and response_path.is_file():
            entry["current_script_replay"] = replay(replay_scripts[case_id], response_path.read_text(), case_dir,
                                                    case_target / "current-script-replay.json", output)
        info["cases"].append(entry)
        seen.add((case_id, iteration))
    for case_id in manifest["cases"]:
        if not any(key[0] == case_id for key in seen):
            info["cases"].append({"case_id": case_id, "status": "NOT_RUN", "execution_state": "not_dispatched",
                                  "reason": "没有 case_started、case_completed 或最终 result；尚未派发，不计为通过"})
    info["case_counts"] = dict(Counter(case["status"] for case in info["cases"]))
    return info


def render(summary: dict) -> str:
    lines = ["# GPT 6.1 定向实测证据", "",
             "with_skill 仅表示已安装目标 Skill，不证明实际加载。原生正文注入、工具读取及宿主 catalog 见 controlled-audit-summary 与各运行 transcript-audit；实际污染审计以主报告为准。",
             "case verdict 原样取自 skill-up result；尚无最终 result 时取 case_completed 事件并标明来源。grading pass_rate 仅为断言统计。",
             "cohort pending 与 case 状态分别记录；RUNNING 表示已派发未完成，NOT_RUN 表示无派发证据。脚本 replay 单独列出，旧 FAIL 保留。",
             "这是 prompt-level with-Skill 实测，不证明生成目标已执行；未覆盖完整复测、without-Skill 对照或 Claude Code 实机行为。输入列为 skill-up 派生口径，不直接代表 CLI 原生 input 或计费；原生字段另见 token-metrics.json。", "",
             "| Run | Case | 原始结果 | 当前脚本 replay | skill-up 派生输入 / 输出 tokens |", "| --- | --- | --- | --- | --- |"]
    for run in summary["runs"]:
        for case in run["cases"]:
            replay_result = case.get("current_script_replay", {}).get("verdict", "未重放")
            lines.append(f"| {run['run']} | {case['case_id']} | {case['status']} | {replay_result} | {case.get('input_tokens', '—')} / {case.get('output_tokens', '—')} |")
    for run in summary["runs"]:
        lines.extend(["", f"## {run['run']}", "", f"运行状态 `{run['state']}`；本地原始目录 `{run['original_directory']}`。",
                      f"工具 `{run['skill_up']}` / `{run['codex']}`；reasoning `{run['reasoning_effort']}`。",
                      f"调用方式 invocation_mode：`{run.get('invocation_mode') or 'unknown（旧运行未记录；不推断为显式调用）'}`；精确 invocation_prefix 见 summary.json 与冻结 manifest。",
                      f"运行时原隔离声明（含旧 skip-only 声明，仅作原始记录）：{run.get('isolation') or '未记录'}",
                      "目标读取、host catalog 与实际污染审计以 transcript-audit 和主报告为准；原声明不等于已证实隔离。", ""])
        for case in run["cases"]:
            lines.append(f"- `{case['case_id']}` 原始 verdict **{case['status']}**。")
            if case.get("status_event_artifact"):
                lines.append(f"  - [状态事件]({case['status_event_artifact']})；{case['reason']}。")
            for assertion in (case.get("grading") or {}).get("assertion_results", []):
                if not assertion.get("passed"):
                    evidence = str(assertion.get("evidence", "")).replace("\n", " ")
                    lines.append(f"  - 未通过断言 `{assertion.get('text')}`：{evidence}")
            for artifact in case.get("artifacts", []):
                if artifact["archive"].endswith(("response.md", "grading.json", "evaluation.json")):
                    lines.append(f"  - [{Path(artifact['archive']).name}]({artifact['archive']})；SHA256 `{artifact['sha256']}`。")
            if case.get("current_script_replay"):
                replay_result = case["current_script_replay"]
                lines.append(f"  - [当前脚本 replay]({replay_result['artifact']})：exit `{replay_result['exit_code']}`，脚本 SHA256 `{replay_result['script_sha256']}`；不修改原 verdict。")
    return "\n".join(lines) + "\n"


def self_test() -> None:
    """离线故障夹具：无 result 的已完成 case 不能被归类为未运行。"""
    with tempfile.TemporaryDirectory(prefix="goal-summary-test-") as temporary:
        root = Path(temporary)
        run = root / "partial-run"
        run.mkdir()
        names = ["completed-fail", "completed-pass", "started-only", "not-started"]
        write_json(run / "manifest.json", {"cases": names, "snapshot_sha256": {}})
        events = []
        for case_id, status in ((names[0], "FAIL"), (names[1], "PASS"), (names[2], None)):
            payload = {"case_id": case_id, "iteration": 1, "configuration": "with_skill"}
            events.append({"event": "case_started", "payload": payload})
            if status:
                # 故意让均分和 status 相反，证明不会从均分猜 verdict。
                events.append({"event": "case_completed", "payload": {**payload, "status": status,
                               "pass_rate": 1 if status == "FAIL" else 0}})
            case_dir = run / "reports/iteration-1" / case_id / "with_skill"
            (case_dir / "outputs/workspace/.goal-task/task").mkdir(parents=True)
            (case_dir / "outputs/response.md").write_text("离线冻结响应\n")
            write_json(case_dir / "grading.json", {"status": "PASS", "summary": {"pass_rate": 1}})
            (case_dir / "outputs/workspace/.goal-task/task/state.md").write_text("partial checkpoint\n")
            (case_dir / "outputs/rollout-DO-NOT-COPY.jsonl").write_text("无须归档的原始轨迹\n")
        (run / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
        output = root / "summary"
        command = [sys.executable, str(Path(__file__).resolve()), "--runs", str(run), "--output", str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        summary = json.loads((output / "summary.json").read_text())
        cohort = summary["runs"][0]
        assert cohort["state"] == "pending"
        assert cohort["invocation_mode"] is None and cohort["invocation_prefix"] is None
        assert "unknown（旧运行未记录" in (output / "summary.md").read_text()
        cases = {case["case_id"]: case for case in cohort["cases"]}
        assert [cases[name]["status"] for name in names] == ["FAIL", "PASS", "RUNNING", "NOT_RUN"]
        assert cases["started-only"]["execution_state"] == "dispatched_incomplete"
        assert cases["not-started"]["execution_state"] == "not_dispatched"
        for name in names[:3]:
            assert len(cases[name]["artifacts"]) == 3  # response、grading、state
            assert (output / cases[name]["status_event_artifact"]).is_file()
            for artifact in cases[name]["artifacts"]:
                assert sha256(output / artifact["archive"]) == artifact["sha256"]
        assert not list(output.rglob("rollout*")) and not list(output.rglob("events.jsonl"))
        second = subprocess.run(command, capture_output=True, text=True)
        assert second.returncode == 2 and "输出目录已存在" in second.stderr
        # 最终 result 优先于此前事件；用例目录已有 partial 产物继续保留。
        write_json(run / "reports/iteration-1/result.json", {"case_results": [
            {"case_id": "completed-fail", "configuration": "with_skill", "status": "ERROR"}]})
        write_json(run / "manifest.json", {"cases": names, "snapshot_sha256": {},
                   "invocation_mode": "explicit", "invocation_prefix": "离线显式调用前缀\n"})
        final_output = root / "summary-final"
        subprocess.run(command[:-1] + [str(final_output)], capture_output=True, text=True, check=True)
        final_cohort = json.loads((final_output / "summary.json").read_text())["runs"][0]
        assert final_cohort["invocation_mode"] == "explicit"
        assert final_cohort["invocation_prefix"] == "离线显式调用前缀\n"
        final_cases = final_cohort["cases"]
        assert [case["status"] for case in final_cases if case["case_id"] == "completed-fail"] == ["ERROR"]
    print("PASS: completed FAIL/PASS、started-only、not-started、partial 白名单、拒绝覆盖及 result 优先；无模型调用")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true", help="运行无模型的 partial-run 故障夹具")
    parser.add_argument("--replay", action="append", default=[], metavar="CASE=SCRIPT",
                        help="仅重放显式可信的确定性脚本；不会重新调用模型或修改 verdict")
    args = parser.parse_args()
    if args.self_test:
        if args.runs or args.output or args.replay:
            parser.error("--self-test 不接受运行或输出参数")
        self_test()
        return 0
    if not args.runs or not args.output:
        parser.error("需要 --runs 和 --output")
    output = args.output.resolve()
    if output.exists():
        parser.error("输出目录已存在；请新建目录以保留每次证据")
    runs = [run.resolve() for run in args.runs]
    if len({run.name for run in runs}) != len(runs):
        parser.error("run 目录末级名称必须唯一")
    scripts = {}
    for specification in args.replay:
        case_id, separator, script = specification.partition("=")
        if not separator or not case_id or not script:
            parser.error("--replay 格式为 CASE=SCRIPT")
        scripts[case_id] = Path(script).resolve()
    output.mkdir(parents=True)
    try:
        summary = {"schema_version": 1, "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "summary_script_sha256": sha256(Path(__file__)), "model_calls": False,
                   "verdict_policy": "最终 case_results[].status 优先；partial case 读取 case_completed.status；started-only 为 RUNNING，无派发证据为 NOT_RUN；replay 不修改原 verdict",
                   "runs": [summarize_run(run, output, scripts) for run in runs]}
        write_json(output / "summary.json", summary)
        (output / "summary.md").write_text(render(summary))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        (output / "INCOMPLETE.txt").write_text(str(error) + "\n")
        parser.exit(1, f"汇总不完整：{error}\n")
    print(f"汇总完成，无模型调用：{output / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
