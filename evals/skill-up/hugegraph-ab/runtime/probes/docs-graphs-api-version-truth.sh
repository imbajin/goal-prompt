#!/usr/bin/env bash
set -euo pipefail

root="$1"
en="$root/content/en/docs/clients/restful-api/graphs.md"
cn="$root/content/cn/docs/clients/restful-api/graphs.md"
[[ -f "$en" && -f "$cn" ]] || exit 2

if grep -qi 'backend.*cassandra\|backend=cassandra' "$en" \
  && grep -qi 'backend.*cassandra\|backend=cassandra' "$cn" \
  && grep -q 'In version 1.7.0, dynamic graph creation would cause a NPE' "$en" \
  && grep -q '1.7.0 版本中，动态创建图会导致 NPE' "$cn"
then
  exit 0
fi
exit 10
