#!/usr/bin/env bash
set -euo pipefail
[[ "${AB_FAKE_MODE:-}" == "1" ]] || { echo "fake oracle requires AB_FAKE_MODE=1" >&2; exit 1; }
[[ $# -eq 3 ]] || { echo "usage: fake-oracle.sh workspace pristine output" >&2; exit 2; }
workspace="$1"
pristine="$2"
output="$3"
[[ -s "$workspace/fake-forwarded-goal.txt" && -d "$pristine" ]] || exit 1
case "${AB_CASE_ID:?}" in
  toolchain-empty-graph-edit)
    checks='{"empty_graph_click":true,"canvas_count":true,"nullable_edit":true,"put_persistence":true,"failure_state":true,"api_contract":true,"component_tests":true,"browser_network":true,"version_truth":true}'
    ;;
  server-hstore-graph-isolation)
    checks='{"rest_namespace":true,"put_isolation":true,"merge_isolation":true,"truncate_isolation":true,"rollback_retry":true,"concurrent_first_write":true,"compatibility":true,"real_tests":true,"scope_quality":true,"validation_review":true}'
    ;;
  docs-graphs-api-version-truth)
    checks='{"version_truth":true,"api_behavior":true,"executable_flows":true,"bilingual_equivalence":true,"site_quality":true,"primary_evidence_scope":true}'
    ;;
  *) exit 1 ;;
esac
python3 -c 'import json,sys; print(json.dumps({"case_id":sys.argv[1],"trusted_oracle":True,"checks":json.loads(sys.argv[2]),"facts":{},"claims":{"complete":True}}))' \
  "$AB_CASE_ID" "$checks" >"$output"
