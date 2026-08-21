#!/usr/bin/env bash
set -euo pipefail
[[ "${AB_FAKE_MODE:-}" == "1" ]] || { echo "fake wrapper is forbidden for real runs" >&2; exit 1; }
[[ -n "${AB_ISOLATION_ATTESTATION:-}" ]] || { echo "missing fake isolation attestation path" >&2; exit 1; }
set +e
"$@"
status=$?
set -e
python3 -c '
import json, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({
    "schema_version": 1,
    "runtime": "deterministic_fake",
    "simulated_only": True,
    "executor_exit_code": int(sys.argv[2]),
}, indent=2) + "\n", encoding="utf-8")
' "$AB_ISOLATION_ATTESTATION" "$status"
exit "$status"
