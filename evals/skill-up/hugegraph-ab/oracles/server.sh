#!/usr/bin/env bash
set -euo pipefail
scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
exec python3 "$scripts_dir/oracle-adapter.py" \
  --case server-hstore-graph-isolation \
  --spec-env HG_AB_SERVER_ORACLE_SPEC \
  "$@"
