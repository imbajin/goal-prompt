# hugegraph-doc behavior rubric

Judge reader-executable, bilingual version truth. Maximum: 100.

| Check key | Observable evidence | Points |
| --- | --- | ---: |
| `version_truth` | 1.5, 1.7, and post-1.7 master behavior is separated without inventing 1.8 | 30 |
| `api_behavior` | Endpoints, Content-Type, auth, bodies, supported backends, status codes, and delete/query behavior match server evidence | 25 |
| `executable_flows` | Each supported version has a separate copyable create/query/delete flow | 15 |
| `bilingual_equivalence` | English and Chinese warnings, version ranges, examples, and semantics agree | 10 |
| `site_quality` | Link validation and `hugo --minify` pass | 10 |
| `primary_evidence_scope` | Server source or isolated smoke supports behavior; edits remain in the four scoped files unless evidence justifies expansion | 10 |

Caps:

- Inventing a released 1.8 caps at 50.
- Writing a post-1.7 fix into the 1.7 release, or claiming auth-enabled 1.7 necessarily has the non-auth creator NPE, caps at 59.
- Editing only one language caps at 75.
- A failed Hugo build caps at 70.
- Site build/link success alone cannot establish API behavior or completion.
