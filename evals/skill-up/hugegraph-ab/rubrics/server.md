# HugeGraph/HStore behavior rubric

Judge observable isolation and real storage evidence, never a preferred patch. Maximum: 100.

| Check key | Observable evidence | Points |
| --- | --- | ---: |
| `rest_namespace` | Auth-enabled HugeGraph 1.7 HStore direct REST creates distinct graphspace/graph/store identities; A marker is invisible in B | 15 |
| `put_isolation` | Real `BusinessHandler.doBatch()` + RocksDB PUTs with the same partition/table/logical key remain isolated; reads use `doGet()` | 12 |
| `merge_isolation` | Real batch MERGE counters never combine across graphs | 8 |
| `truncate_isolation` | Real `truncate()` of B leaves A intact | 8 |
| `rollback_retry` | Actual handler/session failure has no partial visibility and a retry succeeds | 7 |
| `concurrent_first_write` | Multiple new graphs allocate independent valid identities within a bounded timeout, without race/deadlock/reserved namespace | 15 |
| `compatibility` | A preallocated valid graph identity remains readable, with no public API or physical-key format change | 10 |
| `real_tests` | All trusted L1 REST and real RocksDB-backed L2 behavior tests pass; no mock-only substitution | 12 |
| `scope_quality` | Implementation follows the real REST → transaction → batch → store path without unrelated redesign | 7 |
| `validation_review` | The full candidate source completes the required Maven compile | 6 |

Caps and critical failures:

- Without `rest_namespace`, cap at 80 and mark the run incomplete; it may only claim store-core identity isolation.
- Cross-graph read/overwrite/MERGE/truncate leakage, concurrent deadlock, public API or physical-key format change, mock-only evidence, or fabricated version/test evidence is a critical failure.
- A run that claims the complete GraphSpace/graph/store defect fixed without L1 REST evidence is a critical overclaim.
- 1.5 is static compatibility context unless actually run; there is no released Server 1.8.
