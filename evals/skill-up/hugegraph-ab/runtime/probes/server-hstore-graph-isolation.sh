#!/usr/bin/env bash
set -euo pipefail

root="$1"
target="$root/hugegraph-store/hg-store-core/src/main/java/org/apache/hugegraph/store/business/BusinessHandlerImpl.java"
[[ -f "$target" ]] || exit 2

python3 - "$target" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
start = text.find("private class TxBuilderImpl")
end = text.find("public Tx build()", start)
if start < 0 or end < 0:
    raise SystemExit(2)
body = text[start:end]
active = body.count("keyCreator.getKey(this.partId, graph, code, key)") >= 2
active = active and "keyCreator.getKeyOrCreate(this.partId, graph, code, key)" not in body
raise SystemExit(0 if active else 10)
PY
