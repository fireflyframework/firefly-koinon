# Nested ingestion destinations implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload into an existing nested Library folder without changing its destination, weakening ancestry authorization or losing its retained work history.

**Architecture:** Reuse canonical `validated_ancestry`, `PARENTS`, existing depth bounds and tenant-first Catalog mutation serialization. Replace direct-parent assumptions with a complete bounded, current ancestry proof. Keep one bulk destination authority path for admission, staging, worker publication and recovery; align pre-pagination SQL history predicates with that path.

**Tech stack:** Native PyFly DI/repositories/transactions, SQLAlchemy, existing PostgreSQL/SQLite tests, unchanged typed API/SDK destination DTOs.

**Spec:** Root's reviewed requirement: actual nested Library folders, current ancestor authority, fixed project/workspace identity, archive/cycle/depth/escape/move protection, shared publication/recovery behavior and a real PostgreSQL opposing-writer regression. The inbound mapping checkpoint discovered the shared product defect; no connector activation is part of this correction.

## Constraints

- Base `e8993499100c96313e9b2ddea9cc357bc2d0d506`; branch `fix/nested-ingestion-destinations` in an isolated checkout. Do not modify the release12 source or merge main while qualification CI runs.
- Preserve explicit parent ID; no flattening, defaults, duplicate uploads or migration.
- No provider I/O or model work inside a primary authority unit. Keep tenant authority before catalog locks, then existing batch/item/job/native order.
- Retain current workspace/resource/PAT policy; do not invent project ACLs or require write access to every ancestor when the canonical token policy authorizes the selected subtree.
- History authorization is applied before counts and paging, not by dropping unauthorized rows from a fetched page.
- No large install or release packaging; use retained read-only interpreters. Local PostgreSQL tests use an explicitly owned isolated fixture, never a production or Studio service. Preserve its data/evidence and stop the owned server afterward.

## Findings that determine scope

`CatalogService.create` and `CatalogHierarchyService.move` already support nested collection/corpus folders, validate the entire path, enforce scope identity and acquire the tenant lock before changing catalog rows. `BulkAuthority.destination` still requires the selected folder's immediate parent to be the project. Its callers include `FileBatches._scope/create`, `BulkQueue._check/publication` and native recovery preparation. The frontend already sends the actual selected folder ID and its project/workspace IDs.

`BulkRepository.visible_page` repeats the direct-parent condition. `QueryBatchRepository.visible_page` joins the project through the source folder's immediate parent. Changing only admission would make legitimate nested uploads or their dataset query history disappear. These SQL paths need the same complete active ancestry semantics.

## Task1: Canonical destination authority

- [ ] Add failing actual native container cases for nested document and dataset batch creation, preserving exact destination/source parent IDs.
- [ ] Add denial cases for archived ancestor, broken link, cycle, excessive folder depth, mixed tenant/project/workspace, stale expected scope and a token limited outside the selected subtree.
- [ ] Add a focused typed catalog ancestry read/lock helper, using bounded ancestor retrieval and `populate_existing` after canonical tenant admission. Lock the complete observed path in stable ID order on writes. Never lock a descendant before the tenant.
- [ ] Reuse `validated_ancestry` over current scoped rows with canonical per-node read authorization. Require selected kind collection/corpus, exact terminal project/workspace IDs and current folder depth bound. Apply catalog/ingest write permission and current resource restriction to the selected destination using existing policy.
- [ ] Use the same method in existing callers, without adding endpoint-specific checks. Run existing bulk admission/staging/recovery tests and the new regression matrix.

## Task2: Retained history parity

- [ ] Add failing SQL-backed cases showing nested batches and dataset-query history remain visible, with accurate totals across multiple pages.
- [ ] Introduce a small shared SQL ancestry predicate/CTE for selected folder roots. Seed from the already scoped operation candidates, walk only their bounded parent paths, and require a complete active folder/project/workspace path with constant tenant/scope. Do not enumerate unrelated workspace contents.
- [ ] Apply it to both history repositories before count/page operations; keep original owner/token and per-item/native-reference predicates.
- [ ] Test removal of ancestor authority, archived ancestor, malformed scope and cycle/depth exhaustion excludes rows and totals; compare SQL admission with the canonical object-path cases.

## Task3: PostgreSQL publication and movement race

- [ ] Use the existing native bulk fixture against an explicitly owned local PostgreSQL database. Retain baseline/red/green logs and exact server identity.
- [ ] Test a catalog move/archive that acquires the tenant lock before the worker: the worker observes the committed current ancestry and either permits only the same valid scope or rejects before native publication.
- [ ] Test the reverse order: worker destination/publication fence holds tenant/path locks, concurrent Catalog mutation waits, then completes or receives the existing busy-state refusal after the worker transaction ends. Assert no deadlock, no retargeted receipt and no unauthorized native publication.
- [ ] Exercise the recovery path against the same nested destination and a later revoked/archived path. Do not simulate success by bypassing the native queue guard.

## Task4: Review and delivery

- [ ] Run scoped Ruff/Pyright and meaningful native suites; verify unchanged API/Python/TypeScript/Java/MCP wire contracts rather than regenerating unrelated SDK files.
- [ ] Update the public Library/upload guide only if it currently describes a direct-project limitation. Record exact qualification and remaining gaps.
- [ ] Obtain independent/root review before focused commit/push. Do not merge into main during the release qualification freeze.

## Review focus

Reusing a cached ORM/snapshot ancestor after waiting on a lock; authorizing only the leaf while an ancestor is archived; reducing subtree PAT permissions by requiring ancestor write grants; excluding valid nested history only after pagination; and publication/move lock inversion are the principal failure modes. PostgreSQL testing is mandatory evidence for the concurrency claims, while controlled tests are not live provider or deployment acceptance.

## Implemented checkpoint and qualification

The canonical authority and both scoped history predicates are implemented. Existing API/SDK/MCP destination DTOs and `BulkAuthority.item` remain unchanged. Invalid ancestry retains the bulk policy contract `AccessDenied/ACCESS_DENIED`; recovery rejects before native inspection, and a denied worker never calls reserve/inspect/execute or automatically claims the item again. The preexisting executor retains its conservative reconciliation state because earlier attempts can have native effects.

The final bulk, bulk-query and Catalog source suite passes 236 tests with 38 environment-gated skips. Four additional explicit PostgreSQL tests pass against isolated databases on the owned shared test server: archive before publication, publication before a busy-folder move, committed empty-folder move before admission, and nested dataset-query history with ancestor archive. They observe real PostgreSQL lock waits and preserve exact destination IDs. No parser/model throughput or deployment claim follows from these tests.

Scoped Ruff and Pyright pass; strict MkDocs and the generated-site checker pass. Two native test fixtures now explicitly load bootstrap grant metadata because selected migration tests can register a contact FK before that target table is imported. A failing selected-suite run and the successful ordinary pytest rerun were retained; no production schema or environment was changed to make the test pass.

Root reviewed the production authority/CTE changes without a blocking finding and requested the policy exception regression above. Main merges remain deferred during release qualification. The preexisting PAT descendant-expansion CTEs remain a separate performance follow-up; this change adds only bounded ancestor walks seeded by scoped operation candidates and makes no constant-time history claim.
