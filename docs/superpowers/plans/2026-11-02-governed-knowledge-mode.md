# Governed Knowledge Mode Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. This is a pending implementation, not a shipped capability.

**Goal:** Let an administrator request RAG or RLM in Settings while durable preparation preserves the active mode until its prerequisites are ready.

**Architecture:** A tenant-scoped transition records the requested settings, submitting identity, settings revision and durable preparation targets. A kind-filtered coordinator reuses current native artifacts, existing index jobs and committed document sections, then commits settings through compare-and-swap. Existing runtime authority and source provenance remain required on every answer.

**Tech Stack:** Native PyFly services/repositories/transactions, PostgreSQL and SQLite, existing native document lineage/index APIs, typed SDKs, Angular Settings.

**Spec:** The authorized task requires automatic necessary preparation, visible active/requested modes, progress, retry/cancel, preserved permissions and file budgets, and no stale worker activation.

## Constraints and ownership

- Worktree `koinon-governed-knowledge-mode-20261102`, branch `feat/governed-knowledge-mode`, base `8f1a06e`; keep PR115 checkout clean.
- Reserve migration `0044_knowledge_mode_transitions`, following `koinon_0043_ordinary_folders`. Unmerged project-policy work must be renumbered separately.
- Own `organization_knowledge` transition modules, additive native preparation seam, SDK contracts, Settings knowledge-behavior files and their tests/docs.
- Keep existing limits and current authority. No live provider readiness or cost claims without observations.
- No content repair for already qualified views; no index rebuild solely because the answer mode changed.
- Curated RLM remains unsupported unless separately qualified; report the prerequisite explicitly.
- RLM view preparation verifies pinned originals and rebuilds whole views from committed ingestion sections through the existing WholeDocumentReader. It does not invoke embeddings or create an index.
- Legacy sources without a committed ingestion head return SOURCE_VERSION_PREPARATION_REQUIRED with the exact document and existing reprocessing action. Automatic extraction-only lineage for those sources is a separate feature; do not silently configure embeddings or replay an uncertain operation.

## Contract

`POST /knowledge/settings/transitions` accepts the complete desired settings and `expected_revision`, with `Idempotency-Key`. Read status and paged targets separately. Retry and cancel use transition revision preconditions. Ordinary settings PUT remains available for same-mode edits; direct mode changes return `KNOWLEDGE_MODE_TRANSITION_REQUIRED` so older callers cannot bypass preparation.

The header records actor/token, active settings revision/digest, requested settings, job identity, status, stage, revision and timing/count summaries. Target rows record canonical/native workspace and source identities, relevant provider/assignment revisions, source version/extraction pins and child index job identities. Stages are discovery, preflight, view repair, index preparation, final verification and activation. Terminal states are succeeded, failed, cancelled and superseded. Credentials and source contents are not stored in progress data.

Activation revalidates the submitting authority, target generation and current dependencies before a settings CAS. Budget-only settings edits can supersede a pending transition. A cancelled or superseded worker cannot publish settings. Artifact work may be retained for reuse, but it never counts as mode activation.

## Implementation sequence

- [ ] Establish focused baseline; distinguish fixture/import failures from behavior failures.
- [ ] Add failing durable transition tests: identity, idempotency, permissions, one active request, current settings unchanged, stale revision and cancellation fencing. Implement DTO/entity/repository/migration and request/status lifecycle.
- [ ] Add failing preflight tests for exact workspace bindings, missing/disabled roles, current-agent roles, ready artifact reuse, missing recorded views, unsupported curated sources and empty libraries. Implement paged native readiness adapter with observable counts.
- [ ] Add failing coordinator tests for kind-filtered claiming, retries, crashes, actor/token revocation and stale settings. Implement durable coordinator and runtime registration without holding primary transactions during parser/model I/O.
- [x] Add actual recorded-view tests proving original digest, current source/version/extraction pins, guarded publication, exact reuse and no embedding/index calls during view preparation. Preserve existing lineage semantics.
- [ ] Qualify those preparation/publication boundaries on native PostgreSQL, including concurrent cancellation/revocation.
- [ ] Add index orchestration tests proving ready reuse, necessary rebuild, preserved old active pointer and recoverable activation. Reuse existing lifecycle/queue/activation services.
- [ ] Add final readiness/CAS tests: changed provider/source/settings, cancelled lease and new transition prevent activation; successful verification changes mode exactly once.
- [ ] Add API/SDK contracts and Settings active/requested state, polling, prerequisites, retry/cancel and stale-context tests. Generate contracts using repository scripts and verify all SDKs.
- [ ] Document workflow and measured stage counters/durations; distinguish model usage from estimated currency cost. Run focused tests, full lint/types, migration proof on a uniquely owned disposable database and independent review before commit/PR.

## Review focus

- Concurrent source or provider changes between verification and activation must not produce a false ready claim.
- Tenant administrators may not bypass workspace write authority, token ceilings or native aliases while repairing.
- A borrowed current-agent model cannot be claimed live-qualified by tenant-level preflight.
- Growing corpora must use paged durable targets without silently truncating work or counts.
- Legacy originals without recorded views, missing immutable originals and unsupported storage backends need distinct actionable outcomes.


## Implementation checkpoint (unshipped)

The isolated branch now contains the transition API and kind-filtered coordinator, paged discovery and verification, RLM whole-view repair, linked RAG index preparation, SDK contracts and Settings progress/retry/cancel actions. The direct PUT gate is integrated with that journey. The earlier checklist records the implementation sequence; final integration and validation remain review gates.

Index preparation incorporates the provider-outside-transaction work from PR120. Native readiness generation and DDL fencing depend on PR121 and Canon migration22. Primary migration44 adds durable preparation and verification state, coalesced change tracking, immutable index activation attempts and separately CAS-updated resolutions. Both generations use deferred commit invalidation. Final activation keeps the native readiness fence until the primary settings commit; it does not scan the full corpus under the tenant lock.

Verification proceeds in durable pages. Changed workspaces are rechecked from coalesced journals; a very large changed workspace still requires proportional work, and continuous change can delay completion. This is not unlimited capacity or an enterprise throughput qualification.

Cancellation closes the parent immediately. Bounded worker cleanup settles child jobs without enumerating all indexes inside the cancellation transaction. A native pointer already switched requires explicit finish or restore with current authority. Immutable activation receipts remain independently pageable after index reuse, workspace changes and cancellation; they retain the original activation actor, token identifier, admitted revision and native/provider/model pins. Recovery cannot silently replay a model call or rewrite earlier evidence.

Focused local SQLite, PostgreSQL activation/migration, SDK, Settings unit and controlled browser tests have passed. Browser API receipts are controlled fixtures, not live provider acceptance. The corrected checkpoint backend suite passed 3050 tests with 201 infrastructure-dependent skips. After normal integration of main through f65d0957, the focused suite passed 223 tests, including fresh PostgreSQL activation and migration checks, with four infrastructure-dependent skips. Hosted checks and final review remain pending. No production migration or deployment of this feature has occurred. The separate unmerged ACL migration44 must be renumbered before integration.
