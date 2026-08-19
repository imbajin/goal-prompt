#!/usr/bin/env python3
"""Execute reviewed behavior checks and derive boolean oracle evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def load_judge_module():
    spec = importlib.util.spec_from_file_location("hugegraph_ab_judge", SCRIPT_DIR / "judge-run.py")
    if spec is None or spec.loader is None:
        raise ValueError("cannot load judge schema")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def expand_argv(value: Any, replacements: dict[str, str]) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError("oracle argv must be a non-empty string array")
    result: list[str] = []
    for item in value:
        rendered = item
        for marker, replacement in replacements.items():
            rendered = rendered.replace("{" + marker + "}", replacement)
        if "{" in rendered or "}" in rendered:
            raise ValueError(f"unknown oracle placeholder in {item!r}")
        result.append(rendered)
    return result


def run_probe(name: str, config: Any, replacements: dict[str, str], default_timeout: int,
              probe_uid: int, probe_gid: int) -> tuple[bool, dict[str, Any]]:
    if not isinstance(config, dict) or set(config) - {"argv", "timeout_seconds"}:
        raise ValueError(f"invalid oracle probe config: {name}")
    timeout = int(config.get("timeout_seconds", default_timeout))
    if timeout < 1 or timeout > 14400:
        raise ValueError(f"invalid oracle timeout: {name}")
    argv = expand_argv(config.get("argv"), replacements)
    def drop_probe_privileges() -> None:
        os.setgid(probe_gid)
        os.setuid(probe_uid)

    process = subprocess.Popen(
        argv,
        cwd=replacements["workspace"],
        env={"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": "/tmp", "TMPDIR": "/tmp"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        preexec_fn=drop_probe_privileges,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, 15)
            process.communicate(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, 9)
            except ProcessLookupError:
                pass
            process.communicate()
        raise ValueError(f"oracle probe timed out: {name}") from exc
    try:
        os.killpg(process.pid, 15)
        time.sleep(0.2)
        os.killpg(process.pid, 9)
    except ProcessLookupError:
        pass
    result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode("utf-8", errors="replace")[-2000:]
        raise ValueError(f"oracle probe environment failure {name} exit={result.returncode}: {stderr}")
    digest = hashlib.sha256(result.stdout + b"\0" + result.stderr).hexdigest()
    return result.returncode == 0, {
        "exit_code": result.returncode,
        "output_sha256": digest,
        "timeout_seconds": timeout,
    }


def main() -> int:
    judge = load_judge_module()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=tuple(judge.RULES))
    parser.add_argument("--spec", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--pristine", required=True)
    parser.add_argument("--agent-artifacts")
    parser.add_argument("--executor-stdout")
    parser.add_argument("--probe-uid", type=int, default=os.getuid())
    parser.add_argument("--probe-gid", type=int, default=os.getgid())
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        spec = read_object(Path(args.spec).resolve())
        if spec.get("schema_version") != 1 or spec.get("case_id") != args.case:
            raise ValueError("oracle spec schema/case mismatch")
        checks_cfg = spec.get("checks")
        facts_cfg = spec.get("facts")
        claims_cfg = spec.get("claims")
        if not isinstance(checks_cfg, dict) or set(checks_cfg) != set(judge.RULES[args.case]):
            raise ValueError("oracle spec must define every rubric check exactly once")
        if not isinstance(facts_cfg, dict) or set(facts_cfg) != set(judge.FACTS[args.case]):
            raise ValueError("oracle spec must define every fact detector exactly once")
        if not isinstance(claims_cfg, dict) or set(claims_cfg) != set(judge.CLAIMS):
            raise ValueError("oracle spec must define every completion-claim detector exactly once")
        timeout = int(spec.get("default_timeout_seconds", 1800))
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch(mode=0o600, exist_ok=True)
        output.chmod(0o600)
        agent_artifacts = Path(args.agent_artifacts).resolve() if args.agent_artifacts else Path(args.workspace).resolve()
        executor_stdout = Path(args.executor_stdout).resolve() if args.executor_stdout else output.with_suffix(".executor-stdout.txt")
        if not executor_stdout.exists():
            if args.executor_stdout:
                raise ValueError("executor stdout input is missing")
            executor_stdout.touch(mode=0o600)
        if not agent_artifacts.is_dir():
            raise ValueError("agent artifacts input is missing")
        replacements = {
            "workspace": str(Path(args.workspace).resolve()),
            "pristine": str(Path(args.pristine).resolve()),
            "agent_artifacts": str(agent_artifacts),
            "executor_stdout": str(executor_stdout),
            "output": str(output),
        }
        checks: dict[str, bool] = {}
        facts: dict[str, bool] = {}
        claims: dict[str, bool] = {}
        provenance: dict[str, Any] = {"checks": {}, "facts": {}, "claims": {}}
        for name in judge.RULES[args.case]:
            checks[name], provenance["checks"][name] = run_probe(
                name, checks_cfg[name], replacements, timeout, args.probe_uid, args.probe_gid,
            )
        for name in judge.FACTS[args.case]:
            facts[name], provenance["facts"][name] = run_probe(
                name, facts_cfg[name], replacements, timeout, args.probe_uid, args.probe_gid,
            )
        for name in judge.CLAIMS:
            claims[name], provenance["claims"][name] = run_probe(
                name, claims_cfg[name], replacements, timeout, args.probe_uid, args.probe_gid,
            )
        evidence = {
            "schema_version": 2,
            "case_id": args.case,
            "trusted_oracle": True,
            "checks": checks,
            "facts": facts,
            "claims": claims,
            "probe_provenance": provenance,
        }
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        validate = subprocess.run([
            sys.executable, str(SCRIPT_DIR / "judge-run.py"),
            "--case", args.case, "--evidence", str(output), "--validate-only",
        ], check=False)
        return validate.returncode
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
