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

The coordinate-table migration passed 18 rollback-only PostgreSQL checks, including the real seven-reader ingestion path, replacement/reprocessing history and RLS. It stamps the manifest with its creation transaction and admits child mappings only in that transaction. A historical transaction stamp was simulated to verify later-append rejection; the test did not commit fixtures across two transactions. Schema, grants and fixture rows were absent after rollback. A later five-check PostgreSQL exercise used real committed transactions: native CSV intake published exact coordinates, then separate runtime and control transactions rejected additions to a sealed mapping. It used no trigger disabling, transaction-ID rewriting or model calls. Managed application rollout remains pending.

Rollback-only document migration checks have also exercised immutable originals, coherent version/extraction heads, committed knowledge-content guards, 512-character actor identities and the actual lexical-search index. Outbox publisher privileges were checked separately; an operating outbox relay was not qualified. Signed HTTP tests verify exact document version/extraction preconditions before replacement or reprocessing.

Historical origins without a recorded manifest remain unknown. Immutable raw-document integration and the curated publication/retrieval lifecycle are still being qualified. External ingestion-database connectors are not qualified. Current configuration must not fill historical origin gaps.

The typed Python, TypeScript and Java SDK contract covers 137 canonical operations and 254 schemas, with 10 separately qualified retained glossary operations. Source and installed-package checks passed 105 Python tests, 33 TypeScript tests and 829 Java tests, including the local HTTP operation inventory and an external Java 21 consumer. The frozen source and four package artifacts were checked against their recorded hashes. These counts describe the current product API; they do not establish complete replacement of every original domain capability.

The canonical file-append endpoint retains an existing dataset identity and appends all materialized sections as new tables, with a bound of 128 sections. Append mode refuses existing table-name collisions without changing the previous native table, and any materialization failure prevents successful publication. Private intake claims and completed idempotency receipts survive catalog edits and cannot be physically deleted through the catalog API. Exact request replays recheck permissions without repeating native work; changed payloads or file-version inputs are rejected. Pending or failed intake blocks canonical query/schema and affected retained reads. Native sections still commit independently: prior snapshots and files remain preserved, while explicit reconciliation recovery, full native/provider append acceptance and async/bulk intake remain unqualified.

Eleven additional PostgreSQL checks exercised append claims and publication using real primary database transactions and a controlled native port. Separate connections observed row-lock waits, competing claims, durable replay, cancellation, membership/token revocation and rollback of a partially projected result. An independent reviewer reran all eleven checks. This proves canonical transaction behavior; it does not qualify the complete native ingestion pipeline.

The coordinate, exact document-part/revision and current curated contracts are included in that installed-client gate. Managed backend rollout remains a separate acceptance step. Interface fixtures test presentation independently. The standalone structured unit suite passed 592 tests. Its full suite also attempted 126 Docker-dependent integration tests, which failed during environment setup because Docker was unavailable. The isolated PostgreSQL checks above are distinct from that original container-based suite.

Twelve opt-in PostgreSQL regressions passed in a dedicated owned database clone using existing non-superuser roles without RLS bypass. They exercised exact consent, actual native commit, controlled acknowledgement loss, receipt-only reconciliation, primary acknowledgement and retrieval through the lexical corpus. The conversation input was a controlled snapshot over real immutable source parts; no model was called. A second integration reviewer reran all twelve tests and checked their source hashes.

The same checks exercised authorized document parts across workspaces, rejected missing or denied source admission, restored scope after nested reads, exceptions and cancellation, and retained source locks until the destination transaction committed. Direct destination-scoped reads could not see source-workspace rows; foreign-workspace writes were rejected. Revoked originating tokens and changed final source revisions prevented publication. The private fixture database received its own migrations and object grants; managed databases and API processes were unchanged.

These results cover immutable document-part evidence, not every historical citation representation or a live HTTP/browser conversation. The current curated implementation still blocks sharing/export and further derivation from published knowledge until transitive source permissions are qualified.

## Current source checkpoint

The October 28 source checkpoint passed 776 backend tests with 17 explicit infrastructure skips, configured lint/type checks and 12 deployment tests. The frontend passed 238 library and 15 management unit tests, 150 Chromium tests, all builds and the independent packed Angular consumer. Screenshots use controlled API fixtures. Management's initial bundle is 706.64 kB against the existing 500 kB warning threshold; that performance target remains open. Opening Chat defers the 562.55 kB OpenUI renderer until an artifact appears.

A private backup restored into a new database with all 99 recorded table counts and the three original migration heads intact. The clone alone advanced to primary revision 0014, document revision 0020 and structured revision 0017. Seven rehearsal checks covered RLS, immutable guards and exact runtime object capabilities. An isolated current API then passed 14 authenticated SDK read checks with model calls disabled. No migration or application restart was applied to the existing services. Their scheduled session and expired private-file cleanup remained active; the retained conversation and its evidence were checked separately. This rehearsal does not establish ownership recovery, a managed rollout or production acceptance.

The Library metadata projection passed signed HTTP, current-permission and typed-client regressions plus an independent PostgreSQL rollback exercise. Visible child counts use the same access boundary as the list. Numeric metadata rejects booleans, negative or unsafe values; unknown values remain null. Tags admit recorded strings only and preserve custom display case. The catalog uses four fixed SQL statements per nonempty page and one batched author-profile lookup, independently of page size; authentication and permission checks remain separate. This query-count check does not establish production capacity.

## MCP source checkpoint

The separately frozen MCP checkpoint passed 834 backend tests with 17 explicit infrastructure skips, the configured lint and type checks, 12 deployment tests, strict documentation build and site validation. Tests use the official MCP Python SDK over the application transport. They cover current scoped-token authorization, workspace isolation, revocation, single-use OAuth codes, consent, scope upgrades and immutable source identity in returned evidence. The source migration has not been applied to the retained application services.

The desktop package passed its TypeScript check, six transport tests, official MCPB manifest validation and relocation tests against an owned mock server. Its bundle includes the bridge and dependency licenses; the evidence skill is a separate archive. These are package and protocol observations. No extension was installed in a user's active desktop client, and hosted Claude or ChatGPT linking, real identity-provider consent and live cloud access remain unqualified.

## Product acceptance still required

The original capability review still contains partial and missing product workflows, including dataset-append recovery/async/bulk intake, the remaining curated lifecycle transitions and semantic authoring. Complete migration parity, external identity-provider acceptance, production capacity, the product release and publication of this source checkpoint remain separate acceptance steps. The original projects must remain available until the replacement has passed those steps.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
