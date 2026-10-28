# Local qualification boundary

The owned local environment was checked with PostgreSQL 17.11, vector 0.8.7, Redis 8.2.3 and Keycloak 26.8.1. No shared service or global PostgreSQL installation was modified.

| Observed check | Result |
|---|---|
| Native and both preserved knowledge migration histories | Applied through native profiles/personal-token revision and both preserved domain heads |
| Runtime PostgreSQL roles | Non-superuser, no RLS bypass; separate privileged provisioning roles |
| Document knowledge FORCE RLS | No scope hidden; foreign tenant hidden; matching scope visible; wrong-tenant insert rejected; local scope reset |
| Retained Structured knowledge service/repositories | Canonical workspace provision, conflicting tenant rejection, foreign/no-scope read denial, native outer transaction rollback |
| Real browser OIDC | Native state/PKCE/ID-token validation, canonical issuer/sub, cookie introspection |
| Session/bearer separation | Cookie-only API denied; real API access token accepted; wrong-audience ID token denied |
| Five fictional identity users | Expected tenant/role denials, editor write, last-admin protection, immediate membership revocation |
| CSRF and logout | Missing token denied; matching token logout; shared logout visible on both API instances |
| PostgreSQL sessions | Survived process restart; reused by two independent API processes |
| Redis | Authenticated ping and expiring write/read |
| Read-only operator diagnostics | Five existing native datasources, runtime/control role flags, both local storage roundtrips, tenant-bound physical HNSW index including predicate/dimension |
| Configured worker limits | Bounded parallel consumers drain on cancellation/failure; configured native job lease and explicit overrides verified |
| Concurrent PostgreSQL admission | Cap one admits one request across two threads; serialized count reads 0 then 1; provider/agent revision fences and owner-wide token cap rechecked |
| Renamed callback and integrated API | Existing identity realm/client/subjects preserved; real browser OIDC/CSRF/logout and separate signed bearer configuration verified after package rename |
| Headless Python SDK | Source and isolated installed wheel pass contract/stream tests without backend, framework or image dependencies |
| Backup and restore | Private custom archive restored into a new database; three recorded revision heads and fictional tenants inspected |

These observations do not establish live external model/connector acceptance, frontend visual acceptance, Docker image execution, production load/capacity, a published release, or a production restore. Provider readiness must be tested against each configured endpoint/model. The Compose, systemd and proxy files are deployment templates; Docker was unavailable in the local qualification environment.

## Chat and source provenance

The product is pinned to the official pyfly 26.10.12 revision. The released wheel and source archive were checked against their published checksums; the installed wheel also passed the selected native streaming, configuration and OIDC regressions.

One owned private-text conversation was exercised with PostgreSQL and a local model. The browser observed incremental SSE, the persisted answer and the selected file metadata. Reopening that same answer is a read-only replay; it does not establish that every configured provider supports the same workflow.

Separate rollback-only PostgreSQL checks exercised native document hydration and actual Parquet/DuckDB query execution. They verified database identity, canonical and native dataset references, the snapshots actually read, changed current snapshots and foreign-snapshot denial. These checks used no model inference. Interface fixtures test how the audit renders recorded receipts; they do not establish live source-connector acceptance.

The additive structured lineage source has passed isolated PostgreSQL tests for immutable original artifacts, ordered transformations, snapshot bindings, scope isolation and failed-publication rollback. The canonical provenance/history controller has passed signed HTTP and native dependency-resolution tests. Constructor metadata has separate native factory regressions and independent review. These checks do not mean the retained management processes have received the new migrations or code: integrated rollout and replay remain pending.

The source-coordinate reader and canonical API have separate tests for exact snapshot identity, selected cells, row/column pagination, native scope mismatches and token restrictions. Native parser tests cover spreadsheet offsets and multiple sheets, multiline CSV records, JSON paths and other supported structured readers. The mapping describes input positions, not the derivation of individual SQL result cells.

The coordinate-table migration passed 18 rollback-only PostgreSQL checks, including the real seven-reader ingestion path, replacement/reprocessing history and RLS. It stamps the manifest with its creation transaction and admits child mappings only in that transaction. A historical transaction stamp was simulated to verify later-append rejection; the test did not commit fixtures across two transactions. Schema, grants and fixture rows were absent after rollback. Managed application rollout remains pending.

Rollback-only document migration checks have also exercised immutable originals, coherent version/extraction heads, committed knowledge-content guards, 512-character actor identities and the actual lexical-search index. Outbox publisher privileges were checked separately; an operating outbox relay was not qualified. Signed HTTP tests verify exact document version/extraction preconditions before replacement or reprocessing.

Historical origins without a recorded manifest remain unknown. Immutable raw-document integration and the curated publication/retrieval lifecycle are still being qualified. External ingestion-database connectors are not qualified. Current configuration must not fill historical origin gaps.

The typed Python, TypeScript and Java SDK contract covers 136 canonical operations and 251 schemas, with 10 separately qualified retained glossary operations. Source and installed-package checks passed 102 Python tests, 31 TypeScript tests and 822 Java tests, including the local HTTP operation inventory and an external Java 21 consumer. The frozen source and four package artifacts were checked against their recorded hashes. These counts describe the current product API; they do not establish complete replacement of every original domain capability.

The coordinate, exact document-part/revision and current curated contracts are included in that installed-client gate. Managed backend rollout and live PostgreSQL consent, acknowledgement, reconciliation and retrieval remain separate acceptance steps. Interface fixtures test presentation independently. The standalone structured unit suite passed 592 tests. Its full suite also attempted 126 Docker-dependent integration tests, which failed during environment setup because Docker was unavailable. The isolated PostgreSQL checks above are distinct from that original container-based suite.

The current curated implementation explicitly blocks sharing/export and further derivation from published knowledge until transitive source permissions are qualified. Final document-source revalidation across workspaces also needs a PostgreSQL RLS/GUC test before deployment. Source tests do not establish that behavior in the managed runtime.

## Product acceptance still required

The original capability review still contains partial and missing product workflows, including dataset append, curated knowledge lifecycle and semantic authoring. Complete migration parity, external identity-provider acceptance, production capacity, the product release and documentation publication remain separate acceptance steps. The original projects must remain available until the replacement has passed those steps.

Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc. Licensed under Apache-2.0. Made with <3.
