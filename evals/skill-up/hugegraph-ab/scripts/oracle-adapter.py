#!/usr/bin/env python3
"""Run the checked-in command oracle with a trusted, host-only case spec."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--spec-env", required=True)
    parser.add_argument("workspace")
    parser.add_argument("pristine")
    parser.add_argument("output")
    args = parser.parse_args()
    spec_value = os.environ.get(args.spec_env, "")
    if not spec_value:
        print(f"{args.spec_env} must name a reviewed host-only oracle spec", file=sys.stderr)
        return 1
    spec = Path(spec_value).expanduser().resolve()
    if not spec.is_file():
        print(f"trusted oracle spec is not a file: {spec}", file=sys.stderr)
        return 1
    result = subprocess.run([
        sys.executable,
        str(SCRIPT_DIR / "trusted-command-oracle.py"),
        "--case", args.case,
        "--spec", str(spec),
        "--workspace", str(Path(args.workspace).resolve()),
        "--pristine", str(Path(args.pristine).resolve()),
        "--output", str(Path(args.output).resolve()),
    ], check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
