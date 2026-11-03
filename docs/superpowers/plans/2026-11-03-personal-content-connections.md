<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Personal content connections implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Connect personal read-only Microsoft and Google accounts, browse authorized sources and review an explicit Library destination without enabling unsafe imported content.

**Architecture:** koinon owns the concrete source adapters, provider DTOs, delegated OAuth policy, account lifecycle, mappings and reader authority. PyFly supplies existing generic native HTTP streaming, OAuth acquisition, DI, persistence and jobs. Reuse koinon_storage.ClientLifecycle for cancellation-draining transport disposal. Generic framework additions are limited to the response protocol, opt-in auth stripping/error sanitization, public client identity and URI/scope validation wrappers. The user explicitly moved provider-specific code out of the proposed framework PR238; do not merge that PR.

**Tech Stack:** Python3.13, native PyFly HTTP/OAuth and repositories, SQLAlchemy, typed REST/SDK boundaries, existing Angular components.

**Spec:** ../specs/2026-11-02-inbound-document-sync.md

## Constraints and review focus

- No remote mutation methods, importer-token fallback for readers, empty default Library folders, plaintext token DTOs or fake enabled synchronization.
- Stable provider account/drive/item identities; exact callbacks and verified issuer/subject/nonce/state; encrypted rotating refresh credentials.
- Provider I/O outside primary transactions; current destination write authority and per-reader remote download permission.
- Test cross-user/cross-tenant cursor and connection confusion; fail closed on indeterminate access and revoked grants.
- Test signed redirects, token/cookie/header leakage, throttling, cancellation and bounded streams.
- Test empty destinations, overlapping roots, stale mapping review, shortcuts and incomplete pages before activation.
- Source/mock qualification is separate from installed, hosted and real delegated provider acceptance.

## Task1: Product adapter ownership

Files: backend/src/koinon/integrations/content_sources/{dtos,errors,ports,parsing,transport,oauth,microsoft,google_drive}.py; backend/tests/integrations/content_sources/{test_remote_sources,test_source_oauth}.py; inbound spec.

- [x] Port existing provider contract tests to product namespace and verify missing-module failure.
- [x] Move the existing implementation without local-folder/v1 framework domain and without provider dependencies in PyFly.
- [ ] Replace private framework helper imports with reviewed public generic contracts; dependency revision is pinned only after root provides the generic commit.
- [ ] Run product contract tests, Ruff and targeted type checking; record whether generic source override or released dependency was used.

## Task2: Personal account lifecycle and browse

Files: new focused connection settings, entities, repositories, credentials, callback, service, controller and DTO modules under koinon.integrations.content_sources; corresponding backend tests; migration after inspecting current latest native revision.

- [x] Test current identity ownership, encrypted credential binding, callback replay/expiry/issuer/nonce checks and credential-free views before implementing.
- [x] Reuse native OAuth acquisition and existing encrypted-storage conventions with a distinct content-source domain separator.
- [ ] Add paginated account/drive/folder browsing, with SharePoint site discovery separately governed by its required read scope. Never infer readiness from a suffix or unverified account.
- [ ] Exercise session expiry, disconnect, rotated refresh and two-user isolation against actual repositories and native HTTP fixture transport.

## Task3: Destination review and reader fences

Files: mapping DTO/entity/repository/service; canonical read authorization integration points identified from source inspection; tests for all consuming surfaces before activation.

- [x] Test canonical destination write access, reviewed root identity/revision, account-scoped overlap and no-default-folder behavior. Cross-account shared-object overlap remains an activation gate.
- [x] Record mappings without activating ingestion until all output surfaces enforce the requesting reader's own current external authorization.
- [ ] Test candidates before text/model reads plus output/commit rechecks, previews/downloads/audits/exports and remembered context. Never use mapping-owner tokens for another reader.
- [ ] Keep failed or indeterminate checks closed and avoid network I/O while holding primary DB connections.

### Next integration sequence

1. Reuse `BulkAuthority.destination` inside a short primary unit for the selected existing folder. Never infer or create a destination from an empty Library. Keep remote root observations outside that unit, then recheck the connection, exact provider account/configuration and canonical destination before recording a review.
2. Persist the reviewed root identity, destination ancestry, selection/removal policy, configuration binding and expiry as a server-owned review. Paginated enumeration must distinguish known totals from incomplete/unknown totals. The mapping starts inactive; accepting a review cannot bypass the missing ingestion and reader-fence gates.
3. Compare root overlap using current stable identities and folder ancestry, without treating an unreadable parent or incomplete page as absence. Serialize concurrent mapping admissions with existing primary authority locking, then compare the mapping revisions observed before provider I/O. Never hold that lock across provider calls.
4. Persist an immutable origin binding for each admitted local version: provider/tenant/drive/object/version, mapping revision, original content hash, native commit receipt and retirement generation. A reader selects their own connection; a mapping's connection is only the importer's grant and is never a fallback for retrieval.
5. Resolve only bounded locally authorized candidates to origin bindings. `PersonalSourceAccess.check` now supplies fresh remote observations for one selected connection, with at most100 candidates and four concurrent requests per process. Bind those observations to the current mapping/origin revisions in the consuming operation and repeat the remote check at output. Its observation DTO is not a reusable authorization ticket.
6. RAG must admit candidate identities before returning protected text; RLM directory names and metadata need the same candidate gate before model-visible enumeration. `_authorize_search_assets` currently receives all admitted assets, so simply placing remote calls there would create corpus-sized network work. Do not add provider I/O to `Catalog.get`, `_read_chain` or their policy transactions. Coordinate concrete native candidate/reader hooks with the knowledge-mode owner before changing those shared files.
7. Cover Library metadata/preview/download, original/history, model text, sources/audits, export, curated evidence and remembered context before registering public sync routes. A denied or indeterminate candidate must not leak content through another output. Reuse existing capture/output/commit fences while keeping network work outside their database snapshots.

## Task4: User journey and delivery

- [ ] Reuse Library/dialog/settings atoms and truthful capability states; no enabled sync action before server gates.
- [ ] Generate API/SDK/MCP parity from actual registered contracts; document setup and current operational limits.
- [ ] Run meaningful backend/browser cases plus project-required checks and desktop/mobile visual review.
- [ ] Obtain root review before commit; keep live provider acceptance pending until real owned delegated folders are tested.

The durable ingestion/delta worker is a subsequent gated slice of the same spec: mapping review alone does not claim recurring synchronization is delivered.

## Development evidence

The first 139 backend tests pass with an explicit source override for the generic PyFly PR240 contracts. Coverage includes native SQL challenge consumption and refresh CAS, live native session deletion or account changes during OAuth, owner/tenant/account separation, configuration changes during remote calls, uncertain exchange/rotation without replay, verified provider identity and bounded read-only discovery/download transports. Personal browse rechecks connection authority before returning remote metadata and seals expiring continuation state to the owner, tenant, connection and operation. These tests use controlled provider responses; no real delegated grant or recurring import has been qualified. Controller contracts are exercised directly in the test container; application routes and the synchronization action are not activated. Current checks also cover narrowed refresh scopes across two rotations, native PKCE, strict loopback opt-in, separate transfer deadlines and direct Graph content streaming without redirects. Ruff and scoped Pyright pass with the same explicit generic source override.

The migration reservation is `0045`, following `koinon_0044_knowledge_modes`; it must not be executed until the dependency and full reviewed schema are present. The provider-specific framework PR238 remains closed and unmerged. No dependency lock is changed until the generic release is available.

### Mapping and origin persistence checkpoint

The internal persistence slice adds reviewed/inactive mapping records, monotonic object observations and a private origin reservation tied to an existing file-intake item. Admission locks the current connection, then mapping, then object; caller-owned canonical tenant/destination locks must precede these locks. Intake batch/item locks follow the origin fence. Provider I/O never belongs inside these units. A captured credential revision is required per observation, but is not stored as permanent origin authority. Duplicate observations keep their generation; stale observations and excluded objects cannot be readmitted.

The origin reservation exists before intake is queued. It retains provider/account/drive/object/version, mapping revision, generation, local source/asset identities and original hash/size. Recording a successful native receipt is idempotent only for the exact immutable receipt and current origin generation; an invalidated final acknowledgment preserves already recorded native effects for reconciliation. These repository methods do not authorize a destination or release content by themselves.

The controlled SQLite repository suite now totals 195 content-source tests, with 36 new mapping/import cases. Scoped new-source/test Ruff and new-source Pyright pass. This does not establish PostgreSQL concurrency behavior, publication integration or live provider acceptance. Production composition, migration0045, mapping review/overlap admission, durable discovery scheduling, before-publication hooks and all reader surfaces remain unregistered or incomplete. Existing `BulkIntakePort` leases and `BulkQueue.publication` are the integration boundary; do not add a second parser queue or treat an after-commit receipt check as a publication fence. File-batch creation is an initial-import path; synchronized replacement must use a reviewed replacement contract and must not create a second source to simulate an update.


Publication integration must preserve one physical lock order across admissions, cancellation, recovery and native publication. The existing `BulkQueue._check` obtains authority/catalog locks and then `records.fenced` takes bulk locks. The new connection/mapping/object fence belongs after authority/catalog admission and before those bulk locks, not inside the existing publication guard's yield or after `_check`. The new repository intake locks and existing bulk job/item/batch paths must be reconciled explicitly. Require an opposing-writers PostgreSQL regression before activation; SQLite does not prove lock ordering or concurrent fencing. Reuse `knowledge/content.py` and native `document_lineage.replace_document` for synchronized document updates, including expected version/hash/extraction and acknowledgment of chunk invalidation; do not invent a replacement model or duplicate the original Library item.


Independent review found that an acknowledgment could retain an old ORM attempt snapshot while waiting for the object fence. A two-session interleaving reproduced a rewritten commit timestamp. The acknowledgment now reselects and locks the attempt after the connection/mapping/object fences, preserving an already committed receipt and timestamp. This regression exercises stale identity-map behavior; it does not replace the required PostgreSQL opposing-lock-order test.

### Destination review checkpoint

The internal service now composes canonical Library destination authority with bounded remote folder ancestry and inactive persistence. Provider metadata is read outside all database units; a second pass rejects changed ancestry. The final short unit reauthorizes the selected local ancestry, locks and revalidates the captured connection, and compares the mapping inventory before saving a 15-minute review. No unrelated Library contents or other owner's destination are returned. Two roots can be disjoint when the ancestor selection is nonrecursive; equal roots or a recursive ancestor conflict. Review limits fail closed rather than returning a partial absence-of-conflict result. See the specification's internal review section for exact guardrails and the cross-account/remote-consistency limitations.

This is still a review-only development milestone. It does not register a public action, activate a mapping, schedule discovery or bypass any publication/reader gate. The existing before-publication lock-order and opposing-writers PostgreSQL requirements remain unchanged.

Root review verified a canonical destination applicability limit: Library supports nested folders, but `BulkAuthority.destination` currently admits only a collection/corpus directly beneath a project. A native catalog regression proves that nested destinations are refused before provider reads and are never flattened. Generalizing that shared intake contract is outside this checkpoint and remains necessary for nested destination support.
