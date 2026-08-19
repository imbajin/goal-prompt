#!/usr/bin/env python3
"""Deterministic orchestration for the HugeGraph two-stage A/B suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import signal
import shlex
import shutil
import stat
import subprocess
import sys
import threading
import time
from typing import Any
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent
REPO_ROOT = SUITE_DIR.parents[2]
EVAL_WORK = REPO_ROOT / ".eval-work"
CHECKED_EVAL = SUITE_DIR / "eval.yaml"
GOAL_PROMPT_SKILL = REPO_ROOT / "skills" / "goal-prompt"
CASE_IDS = (
    "toolchain-empty-graph-edit",
    "server-hstore-graph-isolation",
    "docs-graphs-api-version-truth",
)
ROLE_NAMES = ("without_skill", "with_skill")
COHORTS = ("deterministic", "pilot", "formal")
RUNTIME_MODEL_KEY_MARKER = "__HG_AB_RUNTIME_MODEL_KEY__"
ACTIVE_SERVICE_CLEANUPS: list[dict[str, Any]] = []


class TerminationRequested(BaseException):
    def __init__(self, signum: int):
        super().__init__(f"termination signal {signum}")
        self.signum = signum


AGENT_ENV_ALLOWLIST = (
    "PATH",
    "LANG",
    "LC_ALL",
    "JAVA_HOME",
    "MAVEN_HOME",
    "M2_HOME",
    "NODE_HOME",
    "NVM_BIN",
    "NVM_DIR",
    "PNPM_HOME",
)


class SuiteError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SuiteError(message)


def checked_case(case_id: str) -> Path:
    if case_id not in CASE_IDS:
        fail(f"unknown case: {case_id}")
    return SUITE_DIR / "cases" / f"{case_id}.yaml"


def require_identifier(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", value):
        fail(f"invalid {label}: {value!r}")
    return value


def require_eval_work(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(EVAL_WORK.resolve())
    except ValueError:
        fail(f"{label} must be under {EVAL_WORK}: {resolved}")
    return resolved


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read JSON {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"expected JSON object in {path}")
    return data


def write_json(path: Path, data: Any, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def clean_agent_env() -> dict[str, str]:
    return {key: os.environ[key] for key in AGENT_ENV_ALLOWLIST if key in os.environ}


def extract_prompt(path: Path) -> bytes:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start = None
    indent = None
    for index, line in enumerate(lines):
        if re.fullmatch(r"\s*prompt:\s*\|\s*\r?\n?", line):
            start = index + 1
            continue
        if start is not None and line.strip():
            indent = len(line) - len(line.lstrip(" "))
            break
    if start is None or indent is None:
        fail(f"cannot locate input.prompt block in {path}")
    out: list[str] = []
    for line in lines[start:]:
        if line.strip() and len(line) - len(line.lstrip(" ")) < indent:
            break
        if line.strip():
            out.append(line[indent:])
        else:
            out.append("\n" if line.endswith("\n") else "")
    result = "".join(out).encode("utf-8")
    if not result:
        fail(f"empty input.prompt in {path}")
    return result


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def stable_digest(value: Any) -> str:
    return digest_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def tree_digest(root: Path, exclude_evidence: bool = False) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if ".git" in rel.parts:
            fail(f"forbidden .git entry in source tree: {path}")
        if exclude_evidence and rel.parts and rel.parts[0] == "version-evidence":
            continue
        if path.is_symlink():
            fail(f"symlinks are not allowed in fixtures: {path}")
        if path.is_file():
            digest.update(str(rel).encode("utf-8") + b"\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        fail(f"source directory does not exist: {source}")
    if any(path.name == ".git" for path in source.rglob(".git")):
        fail(f"source must not contain .git: {source}")
    if any(path.is_symlink() for path in source.rglob("*")):
        fail(f"fixture source must not contain symlinks: {source}")
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", ".eval-work", "__pycache__", "*.pyc"),
    )
    tree_digest(destination)


def make_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        mode = path.stat().st_mode
        if path.is_dir():
            path.chmod(mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH | stat.S_IXUSR)
        else:
            path.chmod(mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    mode = root.stat().st_mode
    root.chmod(mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH | stat.S_IXUSR)


def remove_generated_tree(root: Path) -> None:
    """Remove a suite-owned tree even when its copied fixture is read-only."""
    if not root.exists():
        return
    for path in root.rglob("*"):
        mode = path.stat().st_mode
        if path.is_dir():
            path.chmod(mode | stat.S_IWUSR | stat.S_IXUSR)
        else:
            path.chmod(mode | stat.S_IWUSR)
    root.chmod(root.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
    shutil.rmtree(root)


def load_pair(pair_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    pair_root = require_eval_work(pair_root, "pair root")
    manifest = read_json(pair_root / "manifest.json")
    mapping = read_json(pair_root / "private" / "mapping.json")
    if manifest.get("case_id") not in CASE_IDS:
        fail("pair manifest has an unknown case")
    if manifest.get("cohort") not in COHORTS:
        fail("pair manifest has an unknown cohort")
    if mapping.get("case_id") != manifest.get("case_id") or mapping.get("pair_id") != manifest.get("pair_id"):
        fail("pair mapping does not match manifest identity")
    if mapping.get("cohort") != manifest.get("cohort") or mapping.get("cohort_id") != manifest.get("cohort_id"):
        fail("pair mapping does not match manifest cohort")
    roles = mapping.get("roles")
    if not isinstance(roles, dict) or set(roles) != set(ROLE_NAMES):
        fail("pair mapping must contain exactly without_skill and with_skill")
    if len(set(roles.values())) != 2:
        fail("pair arms must be distinct")
    for arm_id in roles.values():
        if not isinstance(arm_id, str) or not re.fullmatch(r"arm-[0-9a-f]{12}", arm_id):
            fail("invalid anonymous arm id")
        if any(label in arm_id for label in ("with", "without", "control", "treatment")):
            fail("variant label leaked into anonymous arm id")
    return manifest, mapping


def update_cohort_ledger(pair_root: Path, manifest: dict[str, Any], **fields: Any) -> None:
    cohort_id = manifest.get("cohort_id")
    if not cohort_id:
        return
    output_root = pair_root.parents[2]
    ledger_path = output_root / "cohorts" / str(cohort_id) / "ledger.json"
    ledger = read_json(ledger_path)
    entries = ledger.get("pairs")
    if not isinstance(entries, list):
        fail("cohort ledger pairs must be an array")
    matches = [
        item for item in entries
        if isinstance(item, dict)
        and item.get("case_id") == manifest.get("case_id")
        and item.get("pair_id") == manifest.get("pair_id")
    ]
    if len(matches) != 1:
        fail("cohort ledger does not contain exactly one current pair")
    matches[0].update(fields)
    write_json(ledger_path, ledger, 0o600)


def validate_planned_schedule(cohort: str, entries: list[dict[str, Any]]) -> None:
    expected = 3 if cohort == "pilot" else 9
    if len(entries) != expected:
        fail(f"{cohort} cohort must preregister exactly {expected} pairs before execution")
    by_case: dict[str, list[dict[str, Any]]] = {case_id: [] for case_id in CASE_IDS}
    for item in entries:
        case_id = item.get("case_id")
        if case_id not in by_case:
            fail("cohort schedule contains an unknown case")
        by_case[str(case_id)].append(item)
    expected_repeats = {1} if cohort == "pilot" else {1, 2, 3}
    for case_id, items in by_case.items():
        if {item.get("repeat") for item in items} != expected_repeats:
            fail(f"{cohort} cohort has an incomplete repeat schedule for {case_id}")
    for stage in ("prompt", "execution"):
        key = f"planned_{stage}_order"
        if cohort == "pilot":
            first = [str(item.get(key)) for item in entries]
            counts = {order: first.count(order) for order in ("ab", "ba")}
            if sorted(counts.values()) != [1, 2]:
                fail(f"pilot {stage} schedule must be 2/1 balanced")
        else:
            for case_id, items in by_case.items():
                first = [str(item.get(key)) for item in items]
                counts = {order: first.count(order) for order in ("ab", "ba")}
                if sorted(counts.values()) != [1, 2]:
                    fail(f"formal {stage} schedule must be 2/1 balanced for {case_id}")


def require_sealed_cohort_plan(pair_root: Path, manifest: dict[str, Any], stage: str,
                               requested_order: str) -> None:
    if manifest.get("cohort") not in ("pilot", "formal"):
        return
    ledger_path = pair_root.parents[2] / "cohorts" / str(manifest.get("cohort_id")) / "ledger.json"
    ledger = read_json(ledger_path)
    if (ledger.get("schema_version") != 1 or ledger.get("cohort") != manifest.get("cohort")
            or ledger.get("cohort_id") != manifest.get("cohort_id")):
        fail("cohort ledger identity does not match the pair")
    if ledger.get("sealed") is not True:
        fail("real cohort must preregister and seal its complete balanced schedule before execution")
    matches = [
        item for item in ledger.get("pairs", [])
        if isinstance(item, dict)
        and item.get("case_id") == manifest.get("case_id")
        and item.get("pair_id") == manifest.get("pair_id")
    ]
    if len(matches) != 1 or matches[0].get(f"planned_{stage}_order") != requested_order:
        fail(f"{stage} order differs from the sealed cohort schedule")


def command_prepare(args: argparse.Namespace) -> None:
    case_id = require_identifier(args.case, "case id")
    checked_case(case_id)
    pair_id = require_identifier(args.pair_id, "pair id")
    cohort = args.cohort
    if cohort not in COHORTS:
        fail(f"unknown cohort: {cohort}")
    if args.repeat < 1:
        fail("--repeat must be positive")
    if args.allow_unprobed and cohort != "deterministic":
        fail("--allow-unprobed is only valid for the deterministic cohort")
    cohort_id = args.cohort_id
    if cohort in ("pilot", "formal"):
        if not cohort_id:
            fail("pilot/formal fixture preparation requires --cohort-id")
        cohort_id = require_identifier(cohort_id, "cohort id")
        if args.force:
            fail("--force is forbidden for preregistered pilot/formal pairs")
        if args.prompt_order not in ("ab", "ba") or args.execution_order not in ("ab", "ba"):
            fail("pilot/formal preparation requires explicit --prompt-order and --execution-order")
    elif cohort_id:
        fail("--cohort-id is only valid for pilot/formal fixtures")
    elif args.prompt_order or args.execution_order:
        fail("planned orders are only valid for pilot/formal fixtures")
    output_root = require_eval_work(Path(args.output_root), "output root")
    ledger: Path | None = None
    ledger_doc: dict[str, Any] | None = None
    if cohort_id:
        ledger = output_root / "cohorts" / cohort_id / "ledger.json"
        if ledger.exists():
            ledger_doc = read_json(ledger)
            if (ledger_doc.get("schema_version") != 1 or ledger_doc.get("cohort") != cohort
                    or ledger_doc.get("cohort_id") != cohort_id):
                fail("cohort ledger schema/type mismatch")
            if ledger_doc.get("sealed") is True:
                fail("cohort schedule is already sealed")
        else:
            ledger_doc = {
                "schema_version": 1, "cohort": cohort, "cohort_id": cohort_id,
                "sealed": False, "pairs": [],
            }
        entries = ledger_doc.get("pairs")
        if not isinstance(entries, list):
            fail("cohort ledger pairs must be an array")
        if any(item.get("case_id") == case_id and item.get("repeat") == args.repeat for item in entries if isinstance(item, dict)):
            fail(f"cohort repeat is already preregistered: {case_id} repeat={args.repeat}")
        expected_count = 3 if cohort == "pilot" else 9
        if len(entries) + 1 == expected_count:
            validate_planned_schedule(cohort, entries + [{
                "case_id": case_id, "pair_id": pair_id, "repeat": args.repeat,
                "planned_prompt_order": args.prompt_order,
                "planned_execution_order": args.execution_order,
            }])
        elif len(entries) + 1 > expected_count:
            fail(f"{cohort} cohort already contains its maximum pair count")
    pair_root = output_root / "pairs" / case_id / pair_id
    require_eval_work(pair_root, "pair root")
    if pair_root.exists():
        if not args.force:
            fail(f"pair already exists: {pair_root}")
        shutil.rmtree(pair_root)

    source = Path(args.source).expanduser().resolve()
    evidence = Path(args.evidence).expanduser().resolve()
    if not evidence.is_dir():
        fail(f"version evidence directory does not exist: {evidence}")

    preflight_status = "unprobed"
    preflight_metadata: dict[str, Any] | None = None
    if args.preflight_metadata:
        preflight_metadata = read_json(Path(args.preflight_metadata).expanduser().resolve())
        preflight_status = str(preflight_metadata.get("status", "unknown"))
        if preflight_metadata.get("case_id") != case_id:
            fail("preflight metadata case does not match")
    elif not args.allow_unprobed:
        fail("--preflight-metadata is required unless --allow-unprobed is used for deterministic fixtures")

    pair_root.mkdir(parents=True)
    pristine_source = pair_root / "private" / "pristine" / "source"
    pristine_evidence = pair_root / "private" / "pristine" / "version-evidence"
    pristine_skill = pair_root / "private" / "pristine" / "goal-prompt"
    pristine_case = pair_root / "private" / "pristine" / "prompt-case.yaml"
    copy_tree(source, pristine_source)
    copy_tree(evidence, pristine_evidence)
    copy_tree(GOAL_PROMPT_SKILL, pristine_skill)
    pristine_case.parent.mkdir(parents=True, exist_ok=True)
    pristine_case.write_bytes(checked_case(case_id).read_bytes())
    source_digest = tree_digest(pristine_source)
    evidence_digest = tree_digest(pristine_evidence)
    if preflight_metadata is not None:
        if preflight_metadata.get("source_sha256") != source_digest:
            fail("source does not match the selected preflight metadata")
        if preflight_metadata.get("version_evidence_sha256") != evidence_digest:
            fail("version-evidence does not match the selected preflight metadata")
        if cohort in ("pilot", "formal"):
            if preflight_status != "active":
                fail(f"{cohort} fixture requires active preflight")
            if preflight_metadata.get("refresh_mode") != "online":
                fail(f"{cohort} fixture requires an online-refreshed preflight")
            if preflight_metadata.get("version_drift") is not False:
                fail(f"{cohort} fixture refuses unresolved version drift")
    raw_request = extract_prompt(checked_case(case_id))

    arm_ids = [f"arm-{secrets.token_hex(6)}", f"arm-{secrets.token_hex(6)}"]
    while arm_ids[0] == arm_ids[1]:
        arm_ids[1] = f"arm-{secrets.token_hex(6)}"
    roles = dict(zip(ROLE_NAMES, arm_ids))

    for arm_id in arm_ids:
        arm_root = pair_root / "arms" / arm_id
        for stage in ("prompt", "execution"):
            workspace = arm_root / stage / "workspace"
            copy_tree(pristine_source, workspace)
            copy_tree(pristine_evidence, workspace / "version-evidence")
            make_read_only(workspace / "version-evidence")
            for name in ("home", "session", "data", "artifacts", "agent-artifacts"):
                (arm_root / stage / name).mkdir(parents=True, exist_ok=True)
            if tree_digest(workspace, exclude_evidence=True) != source_digest:
                fail("source copy identity check failed")
            if tree_digest(workspace / "version-evidence") != evidence_digest:
                fail("version-evidence identity check failed")
        (arm_root / "prompt" / "session" / "raw-request.txt").write_bytes(raw_request)

    make_read_only(pristine_source)
    make_read_only(pristine_evidence)
    make_read_only(pristine_skill)
    pristine_case.chmod(pristine_case.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    mapping = {
        "schema_version": 2,
        "case_id": case_id,
        "pair_id": pair_id,
        "cohort": cohort,
        "cohort_id": cohort_id,
        "repeat": args.repeat,
        "roles": roles,
    }
    write_json(pair_root / "private" / "mapping.json", mapping, 0o600)
    if preflight_metadata is not None:
        write_json(pair_root / "private" / "preflight.json", preflight_metadata, 0o600)
    manifest = {
        "schema_version": 2,
        "case_id": case_id,
        "pair_id": pair_id,
        "cohort": cohort,
        "cohort_id": cohort_id,
        "repeat": args.repeat,
        "preflight_status": preflight_status,
        "preflight_refresh_mode": preflight_metadata.get("refresh_mode") if preflight_metadata else None,
        "arm_ids": sorted(arm_ids),
        "source_sha256": source_digest,
        "version_evidence_sha256": evidence_digest,
        "raw_request_sha256": digest_bytes(raw_request),
        "goal_prompt_sha256": tree_digest(pristine_skill),
        "prompt_case_sha256": file_digest(pristine_case),
        "isolation": {
            "workspace": True,
            "home": True,
            "session": True,
            "data": True,
            "variant_labels_absent_from_arm_paths": True,
        },
    }
    write_json(pair_root / "manifest.json", manifest)
    if ledger is not None and ledger_doc is not None:
        entries = ledger_doc["pairs"]
        entries.append({
            "case_id": case_id,
            "pair_id": pair_id,
            "repeat": args.repeat,
            "pair_root": str(pair_root),
            "status": "registered",
            "planned_prompt_order": args.prompt_order,
            "planned_execution_order": args.execution_order,
        })
        expected_count = 3 if cohort == "pilot" else 9
        if len(entries) == expected_count:
            ledger_doc["sealed"] = True
        write_json(ledger, ledger_doc, 0o600)
    print(pair_root)


def run_process(command: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None,
                timeout_seconds: int = 900) -> subprocess.CompletedProcess[bytes]:
    max_stream_bytes = 8 * 1024 * 1024
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    assert process.stdout is not None and process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout_seconds
    failure: str | None = None
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = f"command timed out after {timeout_seconds}s"
                break
            for key, _ in selector.select(min(remaining, 0.5)):
                chunk = os.read(key.fileobj.fileno(), 64 * 1024)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                stream = captured[str(key.data)]
                stream.extend(chunk)
                if len(stream) > max_stream_bytes:
                    failure = f"command {key.data} exceeded {max_stream_bytes} bytes"
                    break
            if failure:
                break
        if failure:
            terminate_process_group(process)
            raise SuiteError(f"{failure}: {command!r}")
        returncode = process.wait()
        return subprocess.CompletedProcess(
            command, returncode, bytes(captured["stdout"]), bytes(captured["stderr"]),
        )
    except BaseException:
        terminate_process_group(process)
        raise
    finally:
        selector.close()


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    pgid = process.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # Always address the original PGID after the leader wait: the leader may
    # have exited while a descendant in the same group ignored SIGTERM.
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if process.poll() is None:
        process.kill()
        process.wait()


def run_checked(command: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None,
                stdout_path: Path | None = None, timeout_seconds: int = 900) -> subprocess.CompletedProcess[bytes]:
    started = time.monotonic()
    result = run_process(command, cwd=cwd, env=env, timeout_seconds=timeout_seconds)
    elapsed = time.monotonic() - started
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_bytes(result.stdout)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        fail(f"command failed ({result.returncode}, {elapsed:.2f}s): {command!r}\n{stderr}")
    return result


def skill_up_version(skill_up: Path) -> str:
    result = run_checked([str(skill_up), "--version"], timeout_seconds=30)
    return result.stdout.decode("utf-8", errors="replace").strip()


def prompt_role_order(args: argparse.Namespace) -> tuple[str, str]:
    return ROLE_NAMES if args.order == "ab" else tuple(reversed(ROLE_NAMES))


def prompt_dry_run(args: argparse.Namespace) -> None:
    if not args.skill_up:
        fail("--skill-up is required for --dry-run")
    skill_up = Path(args.skill_up).expanduser().resolve()
    if not os.access(skill_up, os.X_OK):
        fail(f"skill-up is not executable: {skill_up}")
    run_checked([str(skill_up), "validate", str(CHECKED_EVAL)])
    listed = run_checked([str(skill_up), "list-cases", str(CHECKED_EVAL)])
    output = listed.stdout.decode("utf-8", errors="replace")
    for case_id in CASE_IDS:
        if case_id not in output:
            fail(f"dry-run case listing is missing {case_id}")
    prospective: list[list[str]] = []
    if args.pair_root:
        require_prompt_policy(args)
        pair_root = require_eval_work(Path(args.pair_root), "pair root")
        manifest, mapping = load_pair(pair_root)
        environment = prompt_environment_block(args)
        for role in prompt_role_order(args):
            runtime_eval = materialize_runtime_skill(pair_root, manifest, mapping, environment, role, args)
            run_checked([str(skill_up), "validate", str(runtime_eval)])
            runtime_listing = run_checked([str(skill_up), "list-cases", str(runtime_eval)]).stdout.decode("utf-8", errors="replace")
            if str(manifest["case_id"]) not in runtime_listing:
                fail("pair-specific temporary config is missing its case")
            prospective.append([
                str(skill_up), "run", str(runtime_eval), "--model", args.model,
                "--output-dir", "<anonymous arm output>",
            ])
    print(json.dumps({
        "dry_run": True,
        "cases": list(CASE_IDS),
        "paired_mode": "two_independent_role_runs" if args.pair_root else "checked_config_only",
        "prompt_order": list(prompt_role_order(args)),
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "skill_up_version": skill_up_version(skill_up),
        "commands": prospective,
    }, ensure_ascii=False))


def run_fake_prompt_pair(pair_root: Path, generator: Path, args: argparse.Namespace) -> None:
    manifest, mapping = load_pair(pair_root)
    frozen_case = pair_root / "private" / "pristine" / "prompt-case.yaml"
    expected = extract_prompt(frozen_case)
    if digest_bytes(expected) != manifest.get("raw_request_sha256"):
        fail("frozen Raw Request changed after fixture preparation")
    if not os.access(generator, os.X_OK):
        fail(f"fake generator is not executable: {generator}")
    order = prompt_role_order(args)
    write_json(pair_root / "private" / "prompt-order.json", {
        "schema_version": 2,
        "order": [mapping["roles"][role] for role in order],
        "policy": {"model": "fake", "reasoning_effort": "fake", "timeout_seconds": args.timeout_seconds, "max_turns": args.max_turns, "max_retries": 0},
    }, 0o600)
    for role in order:
        arm_id = str(mapping["roles"][role])
        stage = pair_root / "arms" / arm_id / "prompt"
        request_path = stage / "session" / "raw-request.txt"
        if request_path.read_bytes() != expected:
            fail("A/B Raw Request bytes differ")
        response_path = stage / "response.txt"
        env = clean_agent_env()
        env.update({
            "HOME": str(stage / "home"),
            "TMPDIR": str(stage / "session"),
            "AB_SESSION_DIR": str(stage / "session"),
            "AB_DATA_DIR": str(stage / "data"),
            "AB_SKILL_MODE": "present" if role == "with_skill" else "absent",
            "AB_FAKE_MODE": "1",
        })
        started = time.monotonic()
        result = run_checked(
            [str(generator), str(request_path), str(stage / "workspace")],
            env=env,
            cwd=stage / "workspace",
            stdout_path=response_path,
        )
        if not result.stdout.strip():
            fail(f"fake generator returned an empty response for anonymous arm {arm_id}")
        metrics = {
            "status": "PASS",
            "duration_seconds": time.monotonic() - started,
            "turns": 1,
            "input_tokens": 0,
            "output_tokens": 0,
            "retries": 0,
            "prompt_score": 80 if role == "with_skill" else 60,
            "raw_request_sha256": digest_bytes(request_path.read_bytes()),
            "response_sha256": digest_bytes(result.stdout),
            "fake": True,
            "model": "fake",
            "reasoning_effort": "fake",
            "max_turns": args.max_turns,
            "timeout_seconds": args.timeout_seconds,
        }
        write_json(stage / "metrics.json", metrics)


def prompt_environment_block(args: argparse.Namespace) -> str:
    if args.runtime == "opensandbox":
        if not args.sandbox_template:
            fail("real prompt execution with opensandbox requires --sandbox-template")
        effort = json.dumps(args.reasoning_effort)
        parsed = urlparse(args.model_base_url)
        provider_host = str(parsed.hostname)
        provider_port = parsed.port or 443
        probe_code = (
            "import json,os,socket,ssl,urllib.request\n"
            f"policy=json.load(urllib.request.urlopen({args.model_policy_url!r},timeout=10))\n"
            f"expected={{'schema_version':1,'identity':{args.model_policy_identity!r},'provider_api_only':True,'public_answer_sources_denied':True,'forward_proxy_disabled':True}}\n"
            "assert all(policy.get(k)==v for k,v in expected.items()), 'invalid model policy'\n"
            "blocked=0\n"
            "for host in ('github.com','raw.githubusercontent.com'):\n"
            "    try:\n"
            "        socket.create_connection((host,443),5).close()\n"
            "    except OSError:\n"
            "        blocked += 1\n"
            "assert blocked==2, 'public answer-source egress was not denied'\n"
            "auth=os.environ.get('OPENAI_API_KEY','')\n"
            "assert auth, 'model API credential was not injected into OpenSandbox'\n"
            "c=None\n"
            "try:\n"
            f"    raw=socket.create_connection(({provider_host!r},{provider_port}),8)\n"
            f"    c=ssl.create_default_context().wrap_socket(raw,server_hostname={provider_host!r})\n"
            "    request=('CONNECT github.com:443 HTTP/1.1\\r\\nHost: github.com:443\\r\\nAuthorization: Bearer '+auth+'\\r\\nProxy-Authorization: Bearer '+auth+'\\r\\nConnection: close\\r\\n\\r\\n').encode()\n"
            "    c.sendall(request)\n"
            "    reply=bytearray()\n"
            "    while b'\\r\\n' not in reply and len(reply)<4096:\n"
            "        chunk=c.recv(min(512,4096-len(reply)))\n"
            "        if not chunk: break\n"
            "        reply.extend(chunk)\n"
            "except OSError:\n"
            "    pass\n"
            "else:\n"
            "    status_line=bytes(reply).split(b'\\r\\n',1)[0]\n"
            "    assert status_line.startswith((b'HTTP/1.1 ',b'HTTP/1.0 ')), 'invalid CONNECT status line'\n"
            "    status=int(status_line.split(b' ',2)[1])\n"
            "    assert not (200 <= status < 300), 'model endpoint accepted a CONNECT tunnel'\n"
            "finally:\n"
            "    c and c.close()\n"
        )
        probe_command = "python3 -c " + shlex.quote(probe_code)
        runtime_secret = RUNTIME_MODEL_KEY_MARKER if getattr(args, "_inject_runtime_model_key", False) else None
        secret_env = (
            "  env:\n"
            f"    OPENAI_API_KEY: {json.dumps(runtime_secret)}\n"
            if runtime_secret else ""
        )
        return (
            "environment:\n"
            "  type: opensandbox\n"
            f"  sandbox_template: {json.dumps(args.sandbox_template)}\n"
            "  use_server_proxy: true\n"
            f"{secret_env}"
            "  kwargs:\n"
            f"    base_url: {json.dumps(args.opensandbox_base_url)}\n"
            "  network_policy: allow_declared\n"
            "  allowed_egress:\n"
            f"    - {json.dumps(args.model_egress_target)}\n"
            "  setup_steps:\n"
            f"    - run: {json.dumps(probe_command)}\n"
            "    - run: >-\n"
            "        mkdir -p \"$HOME/.codex\" &&\n"
            f"        printf '%s\\n' 'model_reasoning_effort = {effort}' > \"$HOME/.codex/config.toml\""
        )
    fail("real prompt execution requires --runtime opensandbox; host none cannot isolate network and docker deny_all also blocks the model control plane")
    return ""


def materialize_runtime_skill(pair_root: Path, manifest: dict[str, Any], mapping: dict[str, Any],
                              environment_block: str, role: str, args: argparse.Namespace) -> Path:
    arm_id = str(mapping["roles"][role])
    runtime_root = pair_root / "private" / "skill-up-runtime" / arm_id
    remove_generated_tree(runtime_root)
    skill_root = runtime_root / "root"
    if role == "with_skill":
        copy_tree(pair_root / "private" / "pristine" / "goal-prompt", skill_root)
    else:
        skill_root.mkdir(parents=True)
    eval_dir = skill_root / "evals"
    skill_root.chmod(skill_root.stat().st_mode | stat.S_IWUSR)
    if eval_dir.exists():
        eval_dir.chmod(eval_dir.stat().st_mode | stat.S_IWUSR)
    cases_dir = eval_dir / "cases"
    fixture_dir = eval_dir / "fixtures" / "repos" / "source"
    cases_dir.mkdir(parents=True)

    case_id = str(manifest["case_id"])
    frozen_case = pair_root / "private" / "pristine" / "prompt-case.yaml"
    if file_digest(frozen_case) != manifest.get("prompt_case_sha256"):
        fail("frozen Prompt case changed after fixture preparation")
    if tree_digest(pair_root / "private" / "pristine" / "goal-prompt") != manifest.get("goal_prompt_sha256"):
        fail("frozen goal-prompt Skill changed after fixture preparation")
    case_text = frozen_case.read_text(encoding="utf-8")
    marker = "expect:\n"
    if marker not in case_text:
        fail("case YAML has no expect block for runtime context insertion")
    case_text = case_text.replace(marker, "context:\n  repo_fixture: evals/fixtures/repos/source\n" + marker, 1)
    (cases_dir / f"{case_id}.yaml").write_text(case_text, encoding="utf-8")

    pristine_source = pair_root / "private" / "pristine" / "source"
    pristine_evidence = pair_root / "private" / "pristine" / "version-evidence"
    if tree_digest(pristine_source) != manifest.get("source_sha256"):
        fail("pristine Prompt source changed after fixture preparation")
    if tree_digest(pristine_evidence) != manifest.get("version_evidence_sha256"):
        fail("pristine Prompt evidence changed after fixture preparation")
    copy_tree(pristine_source, fixture_dir)
    fixture_dir.chmod(fixture_dir.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
    copy_tree(pristine_evidence, fixture_dir / "version-evidence")
    make_read_only(fixture_dir)
    skills_block = "skills: []" if role == "without_skill" else "skills:\n  - source: local_path\n    path: ."
    runtime_eval = f"""schema_version: v1alpha1
{environment_block}
{skills_block}
engine:
  name: codex
  model:
    provider: openai
    name: {json.dumps(args.model)}
    base_url: {json.dumps(args.model_base_url)}
cases:
  files:
    - evals/cases/{case_id}.yaml
  defaults:
    timeout_seconds: {args.timeout_seconds}
    max_turns: {args.max_turns}
  parallelism: 1
  retry_policy:
    max_retries: 0
benchmark:
  enabled: false
report:
  formats: [json]
  artifacts: [transcript]
"""
    (eval_dir / "eval.yaml").write_text(runtime_eval, encoding="utf-8")
    (eval_dir / "eval.yaml").chmod(0o600)
    if role == "without_skill" and (skill_root / "SKILL.md").exists():
        fail("goal-prompt leaked into the without-skill runtime root")
    if role == "with_skill" and not (skill_root / "SKILL.md").is_file():
        fail("with-skill runtime root is missing goal-prompt")
    return eval_dir / "eval.yaml"


def run_skill_up_secret_config(skill_up: Path, action: str, runtime_eval: Path,
                               secret: str, extra_args: list[str], *, env: dict[str, str] | None,
                               timeout_seconds: int) -> subprocess.CompletedProcess[bytes]:
    template = runtime_eval.read_bytes()
    marker = RUNTIME_MODEL_KEY_MARKER.encode("utf-8")
    if marker not in template or secret.encode("utf-8") in template:
        fail("runtime config must contain only the model-key marker")
    payload = template.replace(marker, secret.encode("utf-8"))
    fifo = runtime_eval.parent / f".eval-secret-{secrets.token_hex(8)}.yaml"
    os.mkfifo(fifo, 0o600)
    writer_error: list[BaseException] = []

    def write_config() -> None:
        try:
            with fifo.open("wb", buffering=0) as handle:
                handle.write(payload)
        except BaseException as exc:  # pragma: no cover - surfaced below
            writer_error.append(exc)

    writer = threading.Thread(target=write_config, daemon=True)
    writer.start()
    try:
        result = run_process(
            [str(skill_up), action, str(fifo), *extra_args], env=env, cwd=REPO_ROOT,
            timeout_seconds=timeout_seconds,
        )
    finally:
        fifo.unlink(missing_ok=True)
        writer.join(timeout=2)
    if writer.is_alive() or writer_error:
        fail("failed to deliver the in-memory secret runtime config")
    return result


def import_skill_up_result(pair_root: Path, result_path: Path, role: str, policy: dict[str, Any], cli_exit_code: int) -> None:
    manifest, mapping = load_pair(pair_root)
    result = read_json(result_path)
    case_results = result.get("case_results")
    if not isinstance(case_results, list):
        fail("skill-up result has no case_results array")
    expected_prompt = (pair_root / "arms" / str(mapping["roles"][role]) / "prompt" / "session" / "raw-request.txt").read_text(encoding="utf-8")
    matches = [item for item in case_results if isinstance(item, dict) and item.get("case_id") == manifest["case_id"]]
    if len(matches) != 1:
        fail(f"skill-up result must contain exactly one selected case for {role}")
    item = matches[0]
    if item.get("prompt") != expected_prompt:
        fail(f"skill-up changed Raw Request bytes for {role}")
    response = item.get("response")
    arm_id = str(mapping["roles"][role])
    stage = pair_root / "arms" / arm_id / "prompt"
    response_bytes = response.encode("utf-8") if isinstance(response, str) else b""
    (stage / "response.txt").unlink(missing_ok=True)
    if response_bytes.strip():
        response_bytes = response.encode("utf-8")
        (stage / "response.txt").write_bytes(response_bytes)
    grading = item.get("grading") if isinstance(item.get("grading"), dict) else {}
    summary = grading.get("summary") if isinstance(grading.get("summary"), dict) else {}
    pass_rate = summary.get("pass_rate")
    reported_status = str(item.get("status", "ERROR" if not response_bytes.strip() else "UNKNOWN"))
    failure_kind = None
    if reported_status == "ERROR":
        failure_kind = "prompt_runtime_error"
        failure_class = "environment"
    elif not response_bytes.strip():
        failure_kind = "empty_model_response"
        failure_class = "model"
    else:
        failure_class = None
    metrics = {
        "status": reported_status,
        "failure_kind": failure_kind,
        "failure_class": failure_class,
        "cli_exit_code": cli_exit_code,
        "duration_seconds": float(item.get("duration_ms", 0)) / 1000.0,
        "turns": int(item.get("turns", 0)),
        "input_tokens": int(item.get("input_tokens", 0)),
        "output_tokens": int(item.get("output_tokens", 0)),
        "retries": 0,
        "prompt_score": float(pass_rate) * 100.0 if isinstance(pass_rate, (int, float)) else None,
        "raw_request_sha256": digest_bytes(expected_prompt.encode("utf-8")),
        "response_sha256": digest_bytes(response_bytes) if response_bytes else None,
        "fake": False,
        **policy,
    }
    write_json(stage / "metrics.json", metrics)


def require_prompt_policy(args: argparse.Namespace) -> None:
    if not args.model:
        fail("real or pair-specific prompt dry-run requires explicit --model")
    if not args.reasoning_effort:
        fail("real or pair-specific prompt dry-run requires explicit --reasoning-effort")
    if (not args.model_base_url or not args.model_egress_target or not args.model_policy_url
            or not args.model_policy_identity or not args.opensandbox_base_url):
        fail("real or pair-specific prompt dry-run requires OpenSandbox/model base, egress, and policy identity")
    parsed = urlparse(args.model_base_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        fail("--model-base-url must be a credential-free https URL")
    if args.model_egress_target != parsed.hostname:
        fail("--model-egress-target must exactly match the model base URL hostname")
    policy = urlparse(args.model_policy_url)
    if policy.scheme != "https" or policy.hostname != parsed.hostname or policy.username or policy.password:
        fail("--model-policy-url must be credential-free HTTPS on the model endpoint host")
    control = urlparse(args.opensandbox_base_url)
    if control.scheme != "https" or not control.hostname or control.username or control.password:
        fail("--opensandbox-base-url must be a credential-free HTTPS URL")
    if args.timeout_seconds < 1 or args.max_turns < 1:
        fail("prompt timeout and max turns must be positive")


def validate_prompt_runtime_attestation(args: argparse.Namespace) -> dict[str, Any]:
    if not args.runtime_attestation:
        fail("real prompt execution requires --runtime-attestation")
    path = Path(args.runtime_attestation).expanduser().resolve()
    value = read_json(path)
    expected = {
        "schema_version": 1,
        "runtime": "opensandbox",
        "sandbox_template": args.sandbox_template,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "model_base_url": args.model_base_url,
        "model_egress_target": args.model_egress_target,
        "model_policy_url": args.model_policy_url,
        "model_policy_identity": args.model_policy_identity,
        "opensandbox_base_url": args.opensandbox_base_url,
        "provider_proxy_only": True,
        "public_answer_sources_denied": True,
        "connectivity_probe_required": True,
        "control_plane_authenticated": True,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            fail(f"prompt runtime attestation mismatch for {key}")
    if not isinstance(value.get("sandbox_image_id"), str) or not value["sandbox_image_id"].strip():
        fail("prompt runtime attestation requires the resolved sandbox image identity")
    if not isinstance(value.get("model_auth_identity"), str) or not value["model_auth_identity"].strip():
        fail("prompt runtime attestation requires a non-secret model auth identity")
    if not isinstance(value.get("opensandbox_auth_identity"), str) or not value["opensandbox_auth_identity"].strip():
        fail("prompt runtime attestation requires a non-secret OpenSandbox auth identity")
    return {"sha256": digest_bytes(path.read_bytes()), **expected}


def run_real_prompt_pair(args: argparse.Namespace, pair_root: Path) -> None:
    manifest, mapping = load_pair(pair_root)
    if manifest.get("preflight_status") != "active":
        fail("real model run requires preflight_status=active")
    require_sealed_cohort_plan(pair_root, manifest, "prompt", args.order)
    if not args.skill_up:
        fail("--skill-up is required for a real prompt pair")
    skill_up = Path(args.skill_up).expanduser().resolve()
    if not os.access(skill_up, os.X_OK):
        fail(f"skill-up is not executable: {skill_up}")
    if (pair_root / "private" / "prompt-order.json").exists() or (pair_root / "private" / "skill-up-output").exists():
        fail("prompt pair already has run artifacts; prepare a fresh balanced pair")
    for arm_id in mapping["roles"].values():
        stage = pair_root / "arms" / str(arm_id) / "prompt"
        if (stage / "response.txt").exists() or (stage / "metrics.json").exists():
            fail("prompt arm was already attempted; prepare a fresh balanced pair")
        for name in ("home", "data", "artifacts"):
            if any((stage / name).iterdir()):
                fail(f"prompt {name} is not fresh for anonymous arm {arm_id}")
        session_entries = {path.name for path in (stage / "session").iterdir()}
        if session_entries != {"raw-request.txt"}:
            fail(f"prompt session is not fresh for anonymous arm {arm_id}")
    require_prompt_policy(args)
    if not os.environ.get("HG_AB_OPENSANDBOX_API_KEY"):
        fail("real Prompt execution requires HG_AB_OPENSANDBOX_API_KEY")
    if not os.environ.get("HG_AB_PROMPT_MODEL_API_KEY"):
        fail("real Prompt execution requires HG_AB_PROMPT_MODEL_API_KEY")
    args._inject_runtime_model_key = True
    runtime_attestation = validate_prompt_runtime_attestation(args)
    attestation_source = read_json(Path(args.runtime_attestation).expanduser().resolve())
    runtime_attestation["sandbox_image_id"] = attestation_source["sandbox_image_id"]
    runtime_attestation["model_auth_identity"] = attestation_source["model_auth_identity"]
    runtime_attestation["opensandbox_auth_identity"] = attestation_source["opensandbox_auth_identity"]
    environment = prompt_environment_block(args)
    version = skill_up_version(skill_up)
    order = prompt_role_order(args)
    policy = {
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "model_base_url": args.model_base_url,
        "model_egress_target": args.model_egress_target,
        "model_policy_url": args.model_policy_url,
        "model_policy_identity": args.model_policy_identity,
        "opensandbox_base_url": args.opensandbox_base_url,
        "timeout_seconds": args.timeout_seconds,
        "max_turns": args.max_turns,
        "max_retries": 0,
        "skill_up_version": version,
        "runtime": args.runtime,
        "sandbox_template": args.sandbox_template,
        "runtime_attestation": runtime_attestation,
    }
    write_json(pair_root / "private" / "prompt-order.json", {
        "schema_version": 2,
        "order": [mapping["roles"][role] for role in order],
        "policy": policy,
    }, 0o600)
    failures: list[str] = []
    for role in order:
        arm_id = str(mapping["roles"][role])
        runtime_eval = materialize_runtime_skill(pair_root, manifest, mapping, environment, role, args)
        output_dir = pair_root / "private" / "skill-up-output" / arm_id
        if output_dir.exists():
            shutil.rmtree(output_dir)
        home = pair_root / "arms" / arm_id / "prompt" / "home"
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["OPENSANDBOX_BASE_URL"] = args.opensandbox_base_url
        env["OPENSANDBOX_API_KEY"] = os.environ["HG_AB_OPENSANDBOX_API_KEY"]
        env["OPENAI_API_KEY"] = os.environ["HG_AB_PROMPT_MODEL_API_KEY"]
        try:
            validation = run_skill_up_secret_config(
                skill_up, "validate", runtime_eval, os.environ["HG_AB_PROMPT_MODEL_API_KEY"], [],
                env=env, timeout_seconds=60,
            )
            if validation.returncode != 0:
                fail("secret runtime config validation failed: " + validation.stderr.decode("utf-8", errors="replace"))
            result = run_skill_up_secret_config(
                skill_up, "run", runtime_eval, os.environ["HG_AB_PROMPT_MODEL_API_KEY"],
                ["--model", args.model, "--iteration", "1", "--output-dir", str(output_dir)],
                env=env, timeout_seconds=args.timeout_seconds + 60,
            )
            cli_exit = result.returncode
        except SuiteError as exc:
            write_json(pair_root / "arms" / arm_id / "prompt" / "metrics.json", {
                "status": "ERROR", "failure_kind": "prompt_timeout", "failure_class": "environment",
                "failure": str(exc),
                "retries": 0, "fake": False, **policy,
            })
            failures.append(f"{arm_id}: prompt_timeout")
            continue
        result_path = output_dir / "iteration-1" / "result.json"
        if not result_path.is_file():
            write_json(pair_root / "arms" / arm_id / "prompt" / "metrics.json", {
                "status": "ERROR", "failure_kind": "missing_result", "cli_exit_code": cli_exit,
                "failure_class": "environment",
                "retries": 0, "fake": False, **policy,
            })
            failures.append(f"{arm_id}: missing_result")
            continue
        try:
            import_skill_up_result(pair_root, result_path, role, policy, cli_exit)
        except (SuiteError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            write_json(pair_root / "arms" / arm_id / "prompt" / "metrics.json", {
                "status": "ERROR", "failure_kind": "invalid_result", "cli_exit_code": cli_exit,
                "failure_class": "environment", "failure": str(exc),
                "retries": 0, "fake": False, **policy,
            })
            failures.append(f"{arm_id}: invalid_result")
            continue
        imported = read_json(pair_root / "arms" / arm_id / "prompt" / "metrics.json")
        if imported.get("failure_kind"):
            failures.append(f"{arm_id}: {imported['failure_kind']}")
    update_cohort_ledger(pair_root, manifest,
        prompt_status="terminal",
        prompt_arms={
            str(arm_id): read_json(pair_root / "arms" / str(arm_id) / "prompt" / "metrics.json").get("status")
            for arm_id in manifest["arm_ids"]
        },
    )
    if failures:
        fail("prompt pair preserved failures after attempting both arms: " + ", ".join(failures))


def command_prompt(args: argparse.Namespace) -> None:
    if not args.paired:
        fail("prompt pairing requires explicit --paired")
    if args.dry_run:
        if args.run_models or args.fake_generator:
            fail("--dry-run cannot be combined with model or fake execution")
        prompt_dry_run(args)
        return
    if not args.pair_root:
        fail("--pair-root is required")
    pair_root = require_eval_work(Path(args.pair_root), "pair root")
    if args.fake_generator:
        if args.run_models:
            fail("fake generator cannot be combined with --run-models")
        run_fake_prompt_pair(pair_root, Path(args.fake_generator).expanduser().resolve(), args)
        return
    if not args.run_models:
        fail("real prompt execution requires explicit --run-models")
    run_real_prompt_pair(args, pair_root)


def run_binding(manifest: dict[str, Any], arm_id: str, prompt_metrics: dict[str, Any],
                execution_policy: dict[str, Any], behavior_evidence_sha256: str | None = None) -> str:
    return stable_digest({
        "case_id": manifest["case_id"],
        "pair_id": manifest["pair_id"],
        "cohort": manifest["cohort"],
        "cohort_id": manifest.get("cohort_id"),
        "repeat": manifest["repeat"],
        "anonymous_run_id": arm_id,
        "raw_request_sha256": manifest["raw_request_sha256"],
        "source_sha256": manifest["source_sha256"],
        "version_evidence_sha256": manifest["version_evidence_sha256"],
        "goal_prompt_sha256": manifest["goal_prompt_sha256"],
        "response_sha256": prompt_metrics.get("response_sha256"),
        "behavior_evidence_sha256": behavior_evidence_sha256,
        "execution_policy": execution_policy,
    })


def bind_score(path: Path, manifest: dict[str, Any], arm_id: str,
               prompt_metrics: dict[str, Any], execution_policy: dict[str, Any],
               score_kind: str) -> str:
    score = read_json(path)
    evidence_path = path.parent / "behavior-evidence.json"
    if not evidence_path.is_file():
        fail("trusted behavior evidence is missing before score binding")
    evidence_sha256 = file_digest(evidence_path)
    if score.get("behavior_evidence_sha256") != evidence_sha256:
        fail("judge score does not bind the trusted behavior evidence")
    binding = run_binding(manifest, arm_id, prompt_metrics, execution_policy, evidence_sha256)
    score.update({
        "anonymous_run_id": arm_id,
        "pair_id": manifest["pair_id"],
        "cohort": manifest["cohort"],
        "cohort_id": manifest.get("cohort_id"),
        "repeat": manifest["repeat"],
        "run_binding": binding,
        "behavior_evidence_sha256": evidence_sha256,
        "score_kind": score_kind,
    })
    write_json(path, score)
    return binding


def write_zero_model_score(judge: Path, case_id: str, artifacts: Path,
                           manifest: dict[str, Any], arm_id: str,
                           prompt_metrics: dict[str, Any], execution_policy: dict[str, Any],
                           failure_kind: str) -> str:
    evidence = artifacts / "behavior-evidence.json"
    write_json(evidence, {
        "schema_version": 2,
        "case_id": case_id,
        "trusted_oracle": True,
        "checks": {},
        "facts": {},
        "claims": {},
        "model_failure_kind": failure_kind,
    })
    score_path = artifacts / "score.json"
    run_checked([
        sys.executable, str(judge), "--case", case_id,
        "--evidence", str(evidence), "--output", str(score_path),
    ])
    return bind_score(score_path, manifest, arm_id, prompt_metrics, execution_policy, "model_failure_zero")


def clear_trusted_scoring(artifacts: Path) -> None:
    for name in ("behavior-evidence.json", "score.json"):
        path = artifacts / name
        if path.exists():
            path.unlink()
    for path in artifacts.glob("*.oracle-image-id"):
        path.unlink()


def validate_service_attestation(path: Path, case_id: str, run_id: str,
                                 data_dir: Path, expected_config_identity: str,
                                 used_networks: set[str]) -> dict[str, Any]:
    value = read_json(path)
    expected = {
        "schema_version": 1,
        "case_id": case_id,
        "run_id": run_id,
        "fresh_state": True,
        "exclusive_data_root": True,
        "data_root": str(data_dir.resolve()),
        "service_config_identity": expected_config_identity,
    }
    if any(value.get(key) != item for key, item in expected.items()):
        fail("service attestation does not bind the current anonymous arm and fresh data root")
    network = value.get("network")
    if not isinstance(network, str) or run_id not in network:
        fail("per-arm service network must be unique and include the anonymous run id")
    if network in used_networks:
        fail("service network was reused across anonymous arms")
    used_networks.add(network)
    health = value.get("private_health_urls")
    if not isinstance(health, list) or not health or not all(isinstance(item, str) and item for item in health):
        fail("service attestation requires private health URLs")
    for name in ("model_base_url", "model_policy_url"):
        parsed = urlparse(str(value.get(name, "")))
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            fail(f"invalid service attestation {name}")
    if not isinstance(value.get("model_policy_identity"), str) or not value["model_policy_identity"]:
        fail("service attestation requires model policy identity")
    service_images = value.get("service_image_ids")
    if (not isinstance(service_images, dict) or not service_images
            or not all(isinstance(name, str) and name and isinstance(image, str) and image
                       for name, image in service_images.items())):
        fail("service attestation requires resolved service image identities")
    return value


def run_service_action(harness: Path, action: str, spec: Path, case_id: str,
                       run_id: str, data_dir: Path, output: Path,
                       timeout_seconds: int) -> None:
    run_checked([
        str(harness), action,
        "--spec", str(spec),
        "--case", case_id,
        "--run-id", run_id,
        "--data-dir", str(data_dir),
        "--output", str(output),
    ], env=os.environ.copy(), cwd=REPO_ROOT, timeout_seconds=timeout_seconds)


def service_cleanup_key(harness: Path, spec: Path, case_id: str, run_id: str,
                        data_dir: Path, output: Path) -> tuple[str, ...]:
    return tuple(map(str, (harness, spec, case_id, run_id, data_dir, output)))


def register_service_cleanup(harness: Path, spec: Path, case_id: str, run_id: str,
                             data_dir: Path, output: Path, timeout_seconds: int) -> None:
    ACTIVE_SERVICE_CLEANUPS.append({
        "harness": harness, "spec": spec, "case_id": case_id, "run_id": run_id,
        "data_dir": data_dir, "output": output, "timeout_seconds": timeout_seconds,
    })


def unregister_service_cleanup(harness: Path, spec: Path, case_id: str, run_id: str,
                               data_dir: Path, output: Path) -> None:
    key = service_cleanup_key(harness, spec, case_id, run_id, data_dir, output)
    ACTIVE_SERVICE_CLEANUPS[:] = [
        item for item in ACTIVE_SERVICE_CLEANUPS
        if service_cleanup_key(
            item["harness"], item["spec"], item["case_id"], item["run_id"],
            item["data_dir"], item["output"],
        ) != key
    ]


def cleanup_service(harness: Path | None, spec: Path | None, case_id: str,
                    run_id: str, data_dir: Path, output: Path,
                    timeout_seconds: int, active: bool) -> str | None:
    if not active or harness is None or spec is None:
        return None
    try:
        run_service_action(harness, "cleanup", spec, case_id, run_id, data_dir, output, timeout_seconds)
    except SuiteError as exc:
        return str(exc)
    unregister_service_cleanup(harness, spec, case_id, run_id, data_dir, output)
    return None


def drain_service_cleanups() -> list[str]:
    failures: list[str] = []
    for item in list(ACTIVE_SERVICE_CLEANUPS):
        error = cleanup_service(
            item["harness"], item["spec"], item["case_id"], item["run_id"],
            item["data_dir"], item["output"], item["timeout_seconds"], True,
        )
        if error:
            failures.append(f"{item['case_id']}:{item['run_id']}: {error}")
            write_json(item["output"].parent / "service-cleanup-error.json", {
                "schema_version": 1, "status": "ENVIRONMENT_ERROR",
                "failure_kind": "service_cleanup_error", "failure": error,
                "case_id": item["case_id"], "anonymous_run_id": item["run_id"],
            })
    ACTIVE_SERVICE_CLEANUPS.clear()
    return failures


def verify_isolation_attestation(path: Path, fake: bool) -> dict[str, Any]:
    attestation = read_json(path)
    if fake:
        if attestation.get("runtime") != "deterministic_fake" or attestation.get("simulated_only") is not True:
            fail("deterministic fake requires an explicit simulated-only attestation")
        return attestation
    required = (
        "filesystem_isolated",
        "process_isolated",
        "stage_root_only",
        "version_evidence_read_only_mount",
        "public_egress_denied",
        "private_services_allowed",
        "model_proxy_only",
        "trusted_artifacts_not_mounted",
        "network_probe_passed",
    )
    missing = [name for name in required if attestation.get(name) is not True]
    if missing:
        fail("isolation attestation is missing required guarantees: " + ", ".join(missing))
    if attestation.get("runtime") != "docker_internal_network":
        fail(f"unexpected isolation runtime: {attestation.get('runtime')!r}")
    service_images = attestation.get("service_image_ids")
    if not isinstance(service_images, dict) or not service_images:
        fail("isolation attestation is missing resolved service image identities")
    return attestation


def attested_runtime_failure(attestation: dict[str, Any] | None) -> bool:
    return (
        attestation is None
        or bool(attestation.get("wrapper_failure_kind"))
        or int(attestation.get("executor_exit_code", 125)) not in (0, 10)
    )


def attested_model_failure(attestation: dict[str, Any] | None) -> bool:
    return (
        attestation is not None
        and not attestation.get("wrapper_failure_kind")
        and int(attestation.get("executor_exit_code", 125)) == 10
    )


def command_execute(args: argparse.Namespace) -> None:
    if not args.run_executors and not args.fake:
        fail("downstream execution requires explicit --run-executors")
    pair_root = require_eval_work(Path(args.pair_root), "pair root")
    manifest, mapping = load_pair(pair_root)
    require_sealed_cohort_plan(pair_root, manifest, "execution", args.order)
    executor = Path(args.executor).expanduser().resolve()
    wrapper = Path(args.isolation_wrapper).expanduser().resolve()
    oracle = Path(args.oracle).expanduser().resolve() if args.oracle else None
    oracle_isolation = Path(args.oracle_isolation).expanduser().resolve() if args.oracle_isolation else None
    oracle_spec = Path(args.oracle_spec).expanduser().resolve() if args.oracle_spec else None
    service_harness = Path(args.service_harness).expanduser().resolve() if args.service_harness else None
    service_spec = Path(args.service_spec).expanduser().resolve() if args.service_spec else None
    required_paths: list[tuple[str, Path | None]] = [
        ("executor", executor),
        ("isolation wrapper", wrapper),
    ]
    if args.fake:
        required_paths.append(("fake oracle", oracle))
    else:
        required_paths.extend([
            ("oracle isolation", oracle_isolation),
            ("oracle spec", oracle_spec),
            ("service harness", service_harness),
            ("service spec", service_spec),
        ])
    for label, path in required_paths:
        if path is None:
            fail(f"{label} is required")
        if label.endswith("spec"):
            if not path.is_file() or not os.access(path, os.R_OK):
                fail(f"{label} is not readable: {path}")
        elif not os.access(path, os.X_OK):
            fail(f"{label} is not executable: {path}")
    reviewed_wrapper = (SCRIPT_DIR / "container-isolation.sh").resolve()
    reviewed_oracle_isolation = (SCRIPT_DIR / "oracle-isolation.sh").resolve()
    reviewed_service_harness = (SCRIPT_DIR / "service-harness.py").resolve()
    fake_wrapper = (SUITE_DIR / "fixtures" / "fakes" / "fake-network-wrapper.sh").resolve()
    if args.fake:
        if wrapper != fake_wrapper or manifest.get("cohort") != "deterministic":
            fail("fake execution requires the deterministic cohort and checked-in fake wrapper")
    else:
        if wrapper != reviewed_wrapper:
            fail("real execution requires the checked-in reviewed container isolation wrapper")
        if oracle_isolation != reviewed_oracle_isolation:
            fail("real execution requires the checked-in reviewed oracle isolation wrapper")
        if service_harness != reviewed_service_harness:
            fail("real execution requires the checked-in reviewed per-arm service harness")
        if oracle is not None:
            fail("real execution forbids a host oracle; use --oracle-isolation and --oracle-spec")
        for label, trusted_path in (
            ("executor", executor),
            ("oracle isolation", oracle_isolation),
            ("oracle spec", oracle_spec),
            ("service harness", service_harness),
            ("service spec", service_spec),
        ):
            assert trusted_path is not None
            try:
                trusted_path.relative_to(pair_root)
            except ValueError:
                pass
            else:
                fail(f"real {label} must be outside the anonymous pair tree")
        if manifest.get("cohort") not in ("pilot", "formal") or manifest.get("preflight_status") != "active":
            fail("real execution requires an active pilot/formal fixture")
        if not args.model or not args.reasoning_effort or not args.executor_image or not args.oracle_image:
            fail("real execution requires explicit model/reasoning and executor/oracle images")
        if not os.environ.get("HG_AB_MODEL_API_KEY"):
            fail("real execution requires HG_AB_MODEL_API_KEY for the private provider endpoint")
    if (args.timeout_seconds < 1 or args.oracle_timeout_seconds < 1
            or args.service_timeout_seconds < 1 or args.max_turns < 1 or args.max_retries < 0):
        fail("execution budgets are invalid")
    if args.max_retries != 0:
        fail("automatic downstream retries are disabled; prepare a new balanced pair instead")
    case_id = str(manifest["case_id"])
    judge = SCRIPT_DIR / "judge-run.py"
    pristine = pair_root / "private" / "pristine" / "source"
    expected_source_digest = str(manifest["source_sha256"])
    service_config_identity = "fake"
    if service_spec is not None:
        service_doc = read_json(service_spec)
        service_config_identity = str(service_doc.get("service_config_identity", ""))
        if service_doc.get("schema_version") != 1 or service_doc.get("case_id") != case_id or not service_config_identity:
            fail("service spec schema/case/identity mismatch")

    role_order = ROLE_NAMES if args.order == "ab" else tuple(reversed(ROLE_NAMES))
    pids_limit = int(os.environ.get("HG_AB_PIDS_LIMIT", "1024"))
    memory_limit = os.environ.get("HG_AB_MEMORY_LIMIT", "12g")
    cpu_limit = os.environ.get("HG_AB_CPU_LIMIT", "8")
    if pids_limit <= 0 or not memory_limit or not cpu_limit:
        fail("container resource limits are invalid")
    execution_policy = {
        "model": "fake" if args.fake else args.model,
        "reasoning_effort": "fake" if args.fake else args.reasoning_effort,
        "timeout_seconds": args.timeout_seconds,
        "oracle_timeout_seconds": args.oracle_timeout_seconds,
        "service_timeout_seconds": args.service_timeout_seconds,
        "max_turns": args.max_turns,
        "max_retries": args.max_retries,
        "isolation_wrapper_sha256": file_digest(wrapper),
        "executor_sha256": file_digest(executor),
        "oracle_adapter_sha256": file_digest(oracle) if oracle is not None else None,
        "oracle_isolation_sha256": file_digest(oracle_isolation) if oracle_isolation is not None else None,
        "oracle_spec_sha256": file_digest(oracle_spec) if oracle_spec is not None else None,
        "service_harness_sha256": file_digest(service_harness) if service_harness is not None else None,
        "judge_sha256": file_digest(judge),
        "trusted_command_oracle_sha256": file_digest(SCRIPT_DIR / "trusted-command-oracle.py"),
        "network_probe_sha256": file_digest(SCRIPT_DIR / "container-network-probe.py"),
        "service_spec_sha256": file_digest(service_spec) if service_spec is not None else None,
        "service_config_identity": service_config_identity,
        "executor_image": "fake" if args.fake else args.executor_image,
        "oracle_image": "fake" if args.fake else args.oracle_image,
        "pids_limit": pids_limit,
        "memory_limit": memory_limit,
        "cpu_limit": cpu_limit,
        "goal_prompt_sha256": manifest["goal_prompt_sha256"],
    }
    write_json(pair_root / "private" / "execution-order.json", {
        "schema_version": 2,
        "order": [mapping["roles"][role] for role in role_order],
        "policy": execution_policy,
    }, 0o600)
    failures: list[str] = []
    used_service_networks: set[str] = set()
    for role in role_order:
        arm_id = str(mapping["roles"][role])
        arm_root = pair_root / "arms" / arm_id
        prompt_response = arm_root / "prompt" / "response.txt"
        prompt_metrics = read_json(arm_root / "prompt" / "metrics.json")
        trusted_artifacts = arm_root / "execution" / "artifacts"
        agent_artifacts = arm_root / "execution" / "agent-artifacts"
        if any(trusted_artifacts.iterdir()) or any(agent_artifacts.iterdir()):
            fail("execution artifacts already exist; prepare a fresh pair instead of reusing state")
        prompt_failed = bool(prompt_metrics.get("failure_kind")) or not prompt_response.is_file()
        if prompt_failed:
            if prompt_metrics.get("failure_class") == "environment":
                clear_trusted_scoring(trusted_artifacts)
                write_json(trusted_artifacts / "run.json", {
                    "schema_version": 2, "anonymous_run_id": arm_id, "case_id": case_id,
                    "status": "ENVIRONMENT_ERROR", "failure_kind": "prompt_environment_error",
                    "prompt_metrics": prompt_metrics, "execution_policy": execution_policy,
                    "duration_seconds": 0.0, "attempts": 0, "fake": bool(args.fake),
                })
            else:
                binding = write_zero_model_score(
                    judge, case_id, trusted_artifacts, manifest, arm_id,
                    prompt_metrics, execution_policy, "prompt_failure",
                )
                write_json(trusted_artifacts / "run.json", {
                    "schema_version": 2,
                    "anonymous_run_id": arm_id,
                    "case_id": case_id,
                    "status": "MODEL_FAILURE",
                    "failure_kind": "prompt_failure",
                    "prompt_metrics": prompt_metrics,
                    "execution_policy": execution_policy,
                    "run_binding": binding,
                    "duration_seconds": 0.0,
                    "attempts": 0,
                    "fake": bool(args.fake),
                })
            failures.append(f"{arm_id}: prompt_failure")
            continue
        stage = arm_root / "execution"
        workspace = stage / "workspace"
        if tree_digest(workspace, exclude_evidence=True) != expected_source_digest:
            fail("execution source was not pristine before downstream execution")
        goal_path = stage / "session" / "generated-goal.txt"
        goal_path.write_bytes(prompt_response.read_bytes())
        artifacts = trusted_artifacts
        evidence = artifacts / "behavior-evidence.json"
        executor_stdout = artifacts / "executor-stdout.txt"
        attestation_path = artifacts / "isolation-attestation.json"
        service_attestation_path = artifacts / "service-attestation.json"
        env = clean_agent_env()
        env.update({
            "HOME": str(stage / "home"),
            "TMPDIR": str(stage / "session"),
            "AB_SESSION_DIR": str(stage / "session"),
            "AB_DATA_DIR": str(stage / "data"),
            "AB_RUN_ID": arm_id,
            "AB_CASE_ID": case_id,
            "AB_FAKE_MODE": "1" if args.fake else "0",
            "AB_STAGE_ROOT": str(stage),
            "AB_ISOLATION_ATTESTATION": str(attestation_path),
            "AB_MODEL": execution_policy["model"],
            "AB_REASONING_EFFORT": execution_policy["reasoning_effort"],
            "AB_MAX_TURNS": str(args.max_turns),
        })
        started = time.monotonic()
        expected_prompt_model = "fake" if args.fake else args.model
        expected_prompt_effort = "fake" if args.fake else args.reasoning_effort
        if prompt_metrics.get("model") != expected_prompt_model or prompt_metrics.get("reasoning_effort") != expected_prompt_effort:
            fail("prompt and execution model/reasoning policies differ")
        service_attestation: dict[str, Any] | None = None
        service_active = False
        if not args.fake:
            assert service_harness is not None and service_spec is not None
            assert oracle_isolation is not None and oracle_spec is not None
            try:
                # Register before prepare so an interrupt after partial service
                # creation still reaches the idempotent cleanup contract.
                register_service_cleanup(
                    service_harness, service_spec, case_id, arm_id, stage / "data",
                    service_attestation_path, args.service_timeout_seconds,
                )
                run_service_action(
                    service_harness, "prepare", service_spec, case_id, arm_id,
                    stage / "data", service_attestation_path, args.service_timeout_seconds,
                )
                service_active = True
                service_attestation = validate_service_attestation(
                    service_attestation_path, case_id, arm_id, stage / "data",
                    service_config_identity, used_service_networks,
                )
            except SuiteError as exc:
                clear_trusted_scoring(artifacts)
                cleanup_failure: str | None = None
                try:
                    run_service_action(
                        service_harness, "cleanup", service_spec, case_id, arm_id,
                        stage / "data", service_attestation_path, args.service_timeout_seconds,
                    )
                    unregister_service_cleanup(
                        service_harness, service_spec, case_id, arm_id, stage / "data",
                        service_attestation_path,
                    )
                except SuiteError as cleanup_exc:
                    cleanup_failure = str(cleanup_exc)
                write_json(artifacts / "run.json", {
                    "schema_version": 2, "anonymous_run_id": arm_id, "case_id": case_id,
                    "status": "ENVIRONMENT_ERROR",
                    "failure_kind": "service_cleanup_error" if cleanup_failure else "service_prepare_error",
                    "failure": cleanup_failure or str(exc), "duration_seconds": time.monotonic() - started,
                    "prompt_metrics": prompt_metrics, "execution_policy": execution_policy,
                    "fake": False,
                })
                failures.append(f"{arm_id}: service_prepare_error")
                continue
            env.update({
                "HG_AB_EXECUTOR_IMAGE": str(args.executor_image),
                "HG_AB_PRIVATE_NETWORK": str(service_attestation["network"]),
                "HG_AB_MODEL_BASE_URL": str(service_attestation["model_base_url"]),
                "HG_AB_MODEL_POLICY_URL": str(service_attestation["model_policy_url"]),
                "HG_AB_MODEL_POLICY_IDENTITY": str(service_attestation["model_policy_identity"]),
                "HG_AB_MODEL_API_KEY": os.environ["HG_AB_MODEL_API_KEY"],
                "HG_AB_PRIVATE_HEALTH_URLS": json.dumps(service_attestation["private_health_urls"]),
                "HG_AB_SERVICE_CONFIG_IDENTITY": service_config_identity,
                "HG_AB_SERVICE_ATTESTATION": str(service_attestation_path),
            })
            env.update({
                "HG_AB_PIDS_LIMIT": str(pids_limit),
                "HG_AB_MEMORY_LIMIT": memory_limit,
                "HG_AB_CPU_LIMIT": cpu_limit,
            })
        result: subprocess.CompletedProcess[bytes] | None = None
        attempt_errors: list[str] = []
        for attempt in range(1, args.max_retries + 2):
            try:
                result = run_checked(
                    [str(wrapper), str(executor), str(goal_path), str(workspace), str(agent_artifacts)],
                    env=env,
                    cwd=workspace,
                    stdout_path=executor_stdout,
                    timeout_seconds=args.timeout_seconds,
                )
                break
            except SuiteError as exc:
                attempt_errors.append(str(exc))
        if result is None:
            duration = time.monotonic() - started
            attestation: dict[str, Any] | None = None
            if attestation_path.is_file():
                try:
                    attestation = verify_isolation_attestation(attestation_path, bool(args.fake))
                except SuiteError:
                    attestation = None
            cleanup_error = cleanup_service(
                service_harness, service_spec, case_id, arm_id, stage / "data",
                service_attestation_path, args.service_timeout_seconds, service_active,
            )
            model_failure = attested_model_failure(attestation)
            if model_failure and not cleanup_error:
                binding = write_zero_model_score(
                    judge, case_id, artifacts, manifest, arm_id, prompt_metrics,
                    execution_policy, "executor_error",
                )
                write_json(artifacts / "run.json", {
                    "schema_version": 2, "anonymous_run_id": arm_id, "case_id": case_id,
                    "status": "MODEL_FAILURE", "failure_kind": "executor_error",
                    "failure": attempt_errors[-1], "attempts": len(attempt_errors),
                    "source_before_sha256": expected_source_digest,
                    "duration_seconds": duration, "prompt_metrics": prompt_metrics,
                    "execution_policy": execution_policy, "isolation_attestation": attestation,
                    "run_binding": binding, "fake": bool(args.fake),
                })
            else:
                clear_trusted_scoring(artifacts)
                write_json(artifacts / "run.json", {
                    "schema_version": 2, "anonymous_run_id": arm_id, "case_id": case_id,
                    "status": "ENVIRONMENT_ERROR",
                    "failure_kind": (
                        "service_cleanup_error" if cleanup_error
                        else "executor_environment_error" if attestation is not None
                        else "isolation_error"
                    ),
                    "failure": cleanup_error or attempt_errors[-1],
                    "attempts": len(attempt_errors), "source_before_sha256": expected_source_digest,
                    "duration_seconds": duration, "prompt_metrics": prompt_metrics,
                    "execution_policy": execution_policy, "fake": bool(args.fake),
                })
            failures.append(f"{arm_id}: executor_error")
            continue
        duration = time.monotonic() - started
        try:
            attestation = verify_isolation_attestation(attestation_path, bool(args.fake))
        except SuiteError as exc:
            cleanup_error = cleanup_service(
                service_harness, service_spec, case_id, arm_id, stage / "data",
                service_attestation_path, args.service_timeout_seconds, service_active,
            )
            clear_trusted_scoring(artifacts)
            write_json(artifacts / "run.json", {
                "schema_version": 2, "anonymous_run_id": arm_id, "case_id": case_id,
                "status": "ENVIRONMENT_ERROR",
                "failure_kind": "service_cleanup_error" if cleanup_error else "isolation_error",
                "failure": cleanup_error or str(exc),
                "attempts": len(attempt_errors) + 1, "duration_seconds": duration,
                "prompt_metrics": prompt_metrics, "execution_policy": execution_policy,
                "fake": bool(args.fake),
            })
            failures.append(f"{arm_id}: isolation_error")
            continue
        if digest_bytes(goal_path.read_bytes()) != read_json(arm_root / "prompt" / "metrics.json").get("response_sha256"):
            cleanup_error = cleanup_service(
                service_harness, service_spec, case_id, arm_id, stage / "data",
                service_attestation_path, args.service_timeout_seconds, service_active,
            )
            clear_trusted_scoring(artifacts)
            write_json(artifacts / "run.json", {
                "schema_version": 2, "anonymous_run_id": arm_id, "case_id": case_id,
                "status": "ENVIRONMENT_ERROR", "failure_kind": "goal_integrity_error",
                "failure": cleanup_error or "generated response changed before oracle execution",
                "duration_seconds": duration, "prompt_metrics": prompt_metrics,
                "execution_policy": execution_policy, "isolation_attestation": attestation,
                "fake": bool(args.fake),
            })
            failures.append(f"{arm_id}: goal_integrity_error")
            continue
        oracle_env = clean_agent_env()
        oracle_env.update({
            "AB_CASE_ID": case_id,
            "AB_RUN_ID": arm_id,
            "AB_FAKE_MODE": "1" if args.fake else "0",
        })
        if not args.fake:
            assert service_attestation is not None and oracle_isolation is not None and oracle_spec is not None
            oracle_env.update({
                "HG_AB_ORACLE_IMAGE": str(args.oracle_image),
                "HG_AB_PRIVATE_NETWORK": str(service_attestation["network"]),
            })
            oracle_env.update({
                "HG_AB_PIDS_LIMIT": str(pids_limit),
                "HG_AB_MEMORY_LIMIT": memory_limit,
                "HG_AB_CPU_LIMIT": cpu_limit,
            })
        try:
            if args.fake:
                assert oracle is not None
                run_checked(
                    [str(oracle), str(workspace), str(pristine), str(evidence)],
                    env=oracle_env, cwd=REPO_ROOT,
                    timeout_seconds=args.oracle_timeout_seconds,
                )
            else:
                run_checked(
                    [
                        str(oracle_isolation), case_id, str(oracle_spec), str(workspace), str(pristine),
                        str(agent_artifacts), str(executor_stdout), str(evidence),
                    ],
                    env=oracle_env, cwd=REPO_ROOT,
                    timeout_seconds=args.oracle_timeout_seconds,
                )
                oracle_image_id_path = Path(str(evidence) + ".oracle-image-id")
                if not oracle_image_id_path.is_file():
                    fail("isolated oracle did not attest its image identity")
                attestation["oracle_image_id"] = oracle_image_id_path.read_text(encoding="utf-8").strip()
                oracle_image_id_path.unlink()
        except SuiteError as exc:
            cleanup_error = cleanup_service(
                service_harness, service_spec, case_id, arm_id, stage / "data",
                service_attestation_path, args.service_timeout_seconds, service_active,
            )
            clear_trusted_scoring(artifacts)
            write_json(artifacts / "run.json", {
                "schema_version": 2,
                "anonymous_run_id": arm_id,
                "case_id": case_id,
                "status": "ENVIRONMENT_ERROR",
                "failure_kind": "service_cleanup_error" if cleanup_error else "oracle_environment_error",
                "failure": cleanup_error or str(exc),
                "source_before_sha256": expected_source_digest,
                "duration_seconds": duration,
                "prompt_metrics": prompt_metrics,
                "execution_policy": execution_policy,
                "isolation_attestation": attestation,
                "fake": bool(args.fake),
            })
            failures.append(f"{arm_id}: oracle_environment_error")
            continue
        score_path = artifacts / "score.json"
        try:
            run_checked([
                sys.executable,
                str(judge),
                "--case",
                case_id,
                "--evidence",
                str(evidence),
                "--output",
                str(score_path),
            ])
        except SuiteError as exc:
            cleanup_error = cleanup_service(
                service_harness, service_spec, case_id, arm_id, stage / "data",
                service_attestation_path, args.service_timeout_seconds, service_active,
            )
            clear_trusted_scoring(artifacts)
            write_json(artifacts / "run.json", {
                "schema_version": 2,
                "anonymous_run_id": arm_id,
                "case_id": case_id,
                "status": "ENVIRONMENT_ERROR",
                "failure_kind": "service_cleanup_error" if cleanup_error else "judge_environment_error",
                "failure": cleanup_error or str(exc),
                "source_before_sha256": expected_source_digest,
                "duration_seconds": duration,
                "prompt_metrics": prompt_metrics,
                "execution_policy": execution_policy,
                "isolation_attestation": attestation,
                "fake": bool(args.fake),
            })
            failures.append(f"{arm_id}: judge_environment_error")
            continue
        binding = bind_score(
            score_path, manifest, arm_id, prompt_metrics, execution_policy, "behavior_oracle",
        )
        cleanup_error = cleanup_service(
            service_harness, service_spec, case_id, arm_id, stage / "data",
            service_attestation_path, args.service_timeout_seconds, service_active,
        )
        if cleanup_error:
            clear_trusted_scoring(artifacts)
            write_json(artifacts / "run.json", {
                "schema_version": 2, "anonymous_run_id": arm_id, "case_id": case_id,
                "status": "ENVIRONMENT_ERROR", "failure_kind": "service_cleanup_error",
                "failure": cleanup_error, "source_before_sha256": expected_source_digest,
                "duration_seconds": duration, "prompt_metrics": prompt_metrics,
                "execution_policy": execution_policy, "isolation_attestation": attestation,
                "fake": bool(args.fake),
            })
            failures.append(f"{arm_id}: service_cleanup_error")
            continue
        write_json(artifacts / "run.json", {
            "schema_version": 2,
            "anonymous_run_id": arm_id,
            "case_id": case_id,
            "status": "PASS",
            "executor_exit_code": result.returncode,
            "attempts": len(attempt_errors) + 1,
            "source_before_sha256": expected_source_digest,
            "duration_seconds": duration,
            "prompt_metrics": prompt_metrics,
            "execution_policy": execution_policy,
            "isolation_attestation": attestation,
            "run_binding": binding,
            "fake": bool(args.fake),
        })
    update_cohort_ledger(pair_root, manifest,
        execution_status="terminal",
        terminal_arms={
            str(arm_id): (
                read_json(pair_root / "arms" / str(arm_id) / "execution" / "artifacts" / "run.json").get("status")
                if (pair_root / "arms" / str(arm_id) / "execution" / "artifacts" / "run.json").is_file()
                else "MISSING"
            )
            for arm_id in manifest["arm_ids"]
        },
    )
    if failures:
        fail("downstream pair completed with failures: " + ", ".join(failures))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--case", required=True, choices=CASE_IDS)
    prepare.add_argument("--pair-id", required=True)
    prepare.add_argument("--source", required=True)
    prepare.add_argument("--evidence", required=True)
    prepare.add_argument("--preflight-metadata")
    prepare.add_argument("--allow-unprobed", action="store_true")
    prepare.add_argument("--cohort", choices=COHORTS, default="deterministic")
    prepare.add_argument("--cohort-id")
    prepare.add_argument("--repeat", type=int, default=1)
    prepare.add_argument("--prompt-order", choices=("ab", "ba"))
    prepare.add_argument("--execution-order", choices=("ab", "ba"))
    prepare.add_argument("--output-root", default=str(EVAL_WORK / "hugegraph-ab"))
    prepare.add_argument("--force", action="store_true")
    prepare.set_defaults(func=command_prepare)

    prompt = subparsers.add_parser("prompt")
    prompt.add_argument("--skill-up")
    prompt.add_argument("--pair-root")
    prompt.add_argument("--paired", action="store_true")
    prompt.add_argument("--dry-run", action="store_true")
    prompt.add_argument("--run-models", action="store_true")
    prompt.add_argument("--fake-generator")
    prompt.add_argument("--runtime", choices=("opensandbox",))
    prompt.add_argument("--sandbox-template")
    prompt.add_argument("--runtime-attestation")
    prompt.add_argument("--model")
    prompt.add_argument("--model-base-url")
    prompt.add_argument("--model-egress-target")
    prompt.add_argument("--model-policy-url")
    prompt.add_argument("--model-policy-identity")
    prompt.add_argument("--opensandbox-base-url")
    prompt.add_argument("--reasoning-effort", choices=("minimal", "low", "medium", "high", "xhigh"))
    prompt.add_argument("--order", choices=("ab", "ba"), default="ab")
    prompt.add_argument("--timeout-seconds", type=int, default=900)
    prompt.add_argument("--max-turns", type=int, default=18)
    prompt.set_defaults(func=command_prompt)

    execute = subparsers.add_parser("execute")
    execute.add_argument("--pair-root", required=True)
    execute.add_argument("--executor", required=True)
    execute.add_argument("--isolation-wrapper", required=True)
    execute.add_argument("--oracle")
    execute.add_argument("--oracle-isolation")
    execute.add_argument("--oracle-spec")
    execute.add_argument("--service-harness")
    execute.add_argument("--service-spec")
    execute.add_argument("--executor-image")
    execute.add_argument("--oracle-image")
    execute.add_argument("--run-executors", action="store_true")
    execute.add_argument("--fake", action="store_true")
    execute.add_argument("--order", choices=("ab", "ba"), default="ab")
    execute.add_argument("--model")
    execute.add_argument("--reasoning-effort", choices=("minimal", "low", "medium", "high", "xhigh"))
    execute.add_argument("--timeout-seconds", type=int, default=7200)
    execute.add_argument("--oracle-timeout-seconds", type=int, default=7200)
    execute.add_argument("--service-timeout-seconds", type=int, default=1800)
    execute.add_argument("--max-turns", type=int, default=60)
    execute.add_argument("--max-retries", type=int, default=0)
    execute.set_defaults(func=command_execute)
    return parser


def main() -> int:
    exit_code = 0
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def request_termination(signum: int, _frame: Any) -> None:
        raise TerminationRequested(signum)

    signal.signal(signal.SIGTERM, request_termination)
    try:
        args = build_parser().parse_args()
        args.func(args)
    except SuiteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        exit_code = 1
    except KeyboardInterrupt:
        print("error: interrupted; child process groups and active services were cleaned", file=sys.stderr)
        exit_code = 130
    except TerminationRequested as exc:
        print(f"error: received signal {exc.signum}; cleaning child processes and services", file=sys.stderr)
        exit_code = 128 + exc.signum
    finally:
        cleanup_failures = drain_service_cleanups()
        signal.signal(signal.SIGTERM, previous_sigterm)
        if cleanup_failures:
            for failure in cleanup_failures:
                print(f"error: service_cleanup_error: {failure}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
