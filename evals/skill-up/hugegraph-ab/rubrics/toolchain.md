# Toolchain/Hubble behavior rubric

Judge observable behavior and evidence, never a preferred patch. Maximum: 100.

| Check key | Observable evidence | Points |
| --- | --- | ---: |
| `empty_graph_click` | A real click path opens New → Add Vertex after a successful empty query; edge creation remains unavailable without endpoints | 15 |
| `canvas_count` | One successful POST adds exactly one node and changes count from 0 to 1 | 10 |
| `nullable_edit` | Clicking `alice` exposes an empty schema-declared `description` field even when absent from returned properties | 15 |
| `put_persistence` | Exactly one correct PUT persists `name` and `description`; Server 1.7 re-query confirms both | 15 |
| `failure_state` | POST/PUT failures create no ghost state and preserve honest form/error state | 10 |
| `api_contract` | Correct graphspace/graph URL, method, body, and request count | 10 |
| `component_tests` | Targeted RTL/user-event regression tests pass | 10 |
| `browser_network` | Independent Playwright/browser clicks and network assertions pass without becoming a merge gate | 10 |
| `version_truth` | 1.5/1.7 releases and Toolchain master 1.8 development line are described accurately | 5 |

Caps and penalties:

- If only visual/disabled state changed and the click/API path is not proven, cap at 40.
- If browser click and network evidence is absent, subtract 20.
- If endpoint-free edge operations are enabled, subtract 15.
- If master is called a released 1.8, subtract 10.
- Any cross-graph request, fabricated test result, or claimed completion with a failed persistence re-query is a critical failure.
