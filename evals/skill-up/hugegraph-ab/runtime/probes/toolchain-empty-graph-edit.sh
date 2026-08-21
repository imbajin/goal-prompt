#!/usr/bin/env bash
set -euo pipefail

root="$1"
query="$root/hugegraph-hubble/hubble-fe/src/modules/analysis/QueryResult/Home/index.js"
menu="$root/hugegraph-hubble/hubble-fe/src/modules/analysis/QueryResult/GraphResult/GraphMenubar/index.js"
edit="$root/hugegraph-hubble/hubble-fe/src/modules/component/EditElement/index.js"
[[ -f "$query" && -f "$menu" && -f "$edit" ]] || exit 2

if grep -q 'nonGraphResult ? nonGraphPreview' "$query" \
  && grep -q 'buttonEnableForCanvas2D = showCanvasInfo' "$menu" \
  && grep -q 'buttonEnable={buttonEnableForCanvas2D}' "$menu" \
  && grep -q 'Object.entries(properties)' "$edit" \
  && grep -q 'intersection(Object.keys(obj), arr)' "$edit"
then
  exit 0
fi
exit 10
