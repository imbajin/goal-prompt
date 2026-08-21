#!/usr/bin/env bash
set -euo pipefail
scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
exec python3 "$scripts_dir/oracle-adapter.py" \
  --case toolchain-empty-graph-edit \
  --spec-env HG_AB_TOOLCHAIN_ORACLE_SPEC \
  "$@"
