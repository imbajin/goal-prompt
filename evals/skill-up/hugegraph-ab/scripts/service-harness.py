#!/usr/bin/env python3
"""Run a reviewed per-arm service prepare/cleanup command without a shell."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ALLOWED_ENV = ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT", "XDG_CONFIG_HOME",
               "HG_AB_MODEL_API_KEY", "HG_AB_RUNTIME_PRIVATE_CONFIG")


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def expand_argv(value: Any, replacements: dict[str, str]) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError("service command must be a non-empty argv array")
    rendered: list[str] = []
    for item in value:
        result = item
        for marker, replacement in replacements.items():
            result = result.replace("{" + marker + "}", replacement)
        if "{" in result or "}" in result:
            raise ValueError(f"unknown service placeholder in {item!r}")
        rendered.append(result)
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "reset", "cleanup"))
    parser.add_argument("--spec", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        spec_path = Path(args.spec).resolve()
        spec = read_object(spec_path)
        allowed = {
            "schema_version", "case_id", "service_config_identity",
            "prepare_argv", "reset_argv", "cleanup_argv", "timeout_seconds",
        }
        if set(spec) - allowed:
            raise ValueError("unknown service spec keys")
        if spec.get("schema_version") != 1 or spec.get("case_id") != args.case:
            raise ValueError("service spec schema/case mismatch")
        identity = spec.get("service_config_identity")
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("service_config_identity is required")
        timeout = int(spec.get("timeout_seconds", 900))
        if timeout < 1 or timeout > 14400:
            raise ValueError("invalid service timeout")
        output = Path(args.output).resolve()
        data_dir = Path(args.data_dir).resolve()
        real_controller = any(Path(item).name == "service-controller.py"
                              for key in ("prepare_argv", "reset_argv", "cleanup_argv")
                              for item in spec.get(key, []) if isinstance(item, str))
        if real_controller and output.parent.name != "artifacts":
            raise ValueError("reviewed real services require an execution/artifacts output")
        if output.parent.name == "artifacts":
            expected_data = output.parent.parent / "data"
            if data_dir != expected_data or data_dir.name != "data":
                raise ValueError("service data-dir must be the current arm execution/data directory")
        data_dir.mkdir(parents=True, exist_ok=True)
        replacements = {
            "case": args.case,
            "run_id": args.run_id,
            "data_dir": str(data_dir),
            "output": str(output),
            "service_config_identity": identity,
        }
        argv = expand_argv(spec[f"{args.action}_argv"], replacements)
        env = {key: os.environ[key] for key in ALLOWED_ENV if key in os.environ}
        result = subprocess.run(
            argv,
            cwd=spec_path.parent,
            env=env,
            check=False,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise ValueError(f"service {args.action} failed with exit {result.returncode}")
        if args.action == "prepare" and not output.is_file():
            raise ValueError("service prepare did not write its attestation")
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
