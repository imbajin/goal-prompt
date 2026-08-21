#!/usr/bin/env bash
set -euo pipefail
scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
exec python3 "$scripts_dir/oracle-adapter.py" \
  --case docs-graphs-api-version-truth \
  --spec-env HG_AB_DOCS_ORACLE_SPEC \
  "$@"
