<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Switch document answers between RAG and RLM

Knowledge answers applies to the selected organization. RAG retrieves passages before generating an answer. RLM analyzes recorded document views through bounded model actions. Changing the technique prepares its dependencies before replacing the active organization policy. It does not change source permissions, publish knowledge, or convert datasets into documents.

The preparation receipt distinguishes `active_mode` from `requested_mode`. Existing operations keep their admitted policy snapshot. New operations use the active policy until preparation succeeds and its final revision check commits. A failed, cancelled or superseded request does not activate its requested mode.

## Readiness and necessary work

| Requested mode | Preparation |
| --- | --- |
| RAG | Check effective document answer and embedding assignments. Reuse a compatible qualified active or ready index; create a durable index build only when necessary. Activate the qualified target using current revisions. |
| RLM | Check the effective `documents.rlm` assignment and current document versions. Verify or rebuild recorded whole views from committed ingestion sections. This path makes no embedding calls and creates no vector index. |

Disabled workspace overrides do not silently fall back to organization defaults. Missing provider configuration produces an exact model-configuration prerequisite. Configuration validation and a completed build are not proof that a model will answer every question correctly; qualify representative answers separately.

RLM remains unsupported for curated knowledge (`KNOWLEDGE_RLM_UNQUALIFIED`). An older source without committed version and extraction lineage produces `SOURCE_VERSION_PREPARATION_REQUIRED`, with its document ID and reprocessing action. Finish that source's normal processing before retrying. The transition does not invent historical lineage or configure an embedding provider to repair an RLM view.

View reconstruction verifies the exact original, version, ingestion extraction and hashes. Its current limits are 128 MiB for the original, 64 MiB for the normalized artifact/view and 100,000 parts. A larger file produces an explicit prerequisite; it is not silently truncated. Upload, parser, worker scratch, model and query limits remain separate. See [Library file ingestion](../reference/library-file-ingestion.md) and [Knowledge scaling](../concepts/knowledge-scaling.md).

## Request and follow preparation

Read `GET /api/v1/tenants/{tenant_id}/knowledge/settings`, preserving both policy sections and its revision. Submit the complete `OrganizationKnowledgeSettingsInput` to `POST /api/v1/tenants/{tenant_id}/knowledge/settings/transitions` with a stable `Idempotency-Key`. Organization-level `settings:write` and current credential restrictions are required. A repeated key replays the same request, not another build.

`PUT .../knowledge/settings` continues to update budgets and structured parameters for the active document mode. Changing `answer_mode` through that route returns `KNOWLEDGE_MODE_TRANSITION_REQUIRED`. Structured parameter updates do not qualify or rebuild a Structured corpus.

The transition advances through discovery, model preflight, recorded-view repair or index preparation, verification, and activation. The API exposes its durable job, stage, per-stage milliseconds, counters and precise prerequisites. Read `GET .../transitions/current` or `GET .../transitions/{id}`; read target receipts from `GET .../transitions/{id}/targets?limit=50`. Follow `next_cursor` with `after` until it is null. Each target includes its source or workspace, processing/index job, version pins and applicable action. Never treat the first page as the complete corpus.

Verification reads catalog metadata in pages of at most 100, then reconciles transactional change journals. Changes in one workspace revalidate that workspace; tenant-wide changes can require another tenant scan. `progress_reason: knowledge_changed` and the verification counters expose this work. Counters measure work performed and can count a document again after a change. A continuously changing giant workspace can delay completion; this is not constant-time corpus verification or an unlimited-capacity claim. The final settings transaction checks generations and revisions without rescanning the corpus, and retains the native readiness fence through the primary commit.

With an authenticated Python SDK client:

```python
from koinon_sdk import DocumentKnowledgeSettings, OrganizationKnowledgeSettingsInput

current = await client.organization_knowledge_settings(tenant_id)
change = OrganizationKnowledgeSettingsInput(
    expected_revision=current.revision,
    documents=DocumentKnowledgeSettings.model_validate({
        **current.documents.model_dump(), "answer_mode": "rlm",
    }),
    structured=current.structured,
)
preparation = await client.create_knowledge_mode_transition(
    tenant_id, change, idempotency_key="reviewed-rlm-change-1",
)
progress = await client.knowledge_mode_transition(tenant_id, preparation.id)
page = await client.knowledge_mode_targets(tenant_id, preparation.id, limit=50)
```

TypeScript uses the same contract:

```ts
const current = await client.organizationKnowledge.get(tenantId);
const preparation = await client.knowledgeModes.create(tenantId, {
  expected_revision: current.revision,
  documents: {...current.documents, answer_mode: 'rlm'},
  structured: current.structured,
}, 'reviewed-rlm-change-1');
const progress = await client.knowledgeModes.get(tenantId, preparation.id);
const page = await client.knowledgeModes.targets(tenantId, preparation.id, {limit: 50});
```

Java provides `client.knowledgeModes(tenantId).create(change, idempotencyKey)`, `get(id)`, `current()`, `targets(id, filter)` and `recoveries(id, filter)`, with synchronous and asynchronous methods. [Organization knowledge behavior](organization-knowledge.md) documents the policy parameters; [Headless API and SDK](../guides/headless.md) covers authentication and client setup.

## Failure, retry and cancellation

Retry a failed preparation through `POST .../transitions/{id}/retry` with `KnowledgeModeRevisionInput.expected_revision` from its current receipt. Cancellation uses `POST .../transitions/{id}/cancel` and the same revision contract. Python exposes `retry_knowledge_mode_transition` and `cancel_knowledge_mode_transition`; TypeScript and Java expose `knowledgeModes.retry/cancel`. A newer settings revision supersedes stale preparation rather than letting an older worker overwrite it.

| Receipt | Action |
| --- | --- |
| Source processing incomplete | Inspect the exact document processing job. Complete processing before retrying preparation. |
| Missing historical version | Open the linked document's reprocessing action. Retry after committed version lineage exists. |
| Original hash mismatch or view limit | Inspect the exact source integrity or size prerequisite; the active mode stays unchanged. |
| Missing model binding | Configure the effective role identified by the prerequisite, then retry. |
| Interrupted index qualification or unresolved build outcome | Inspect the linked job and provider outcome. Explicit retry can repeat an uncommitted provider call and its usage. |
| Curated knowledge with requested RLM | Keep RAG; removing or ignoring evidence automatically is not a valid repair. |
| Newer organization settings | Reload and review a new request against the current revision. |

Committed results are reconciled before another attempt. Durable jobs and publication fences prevent stale publication, but do not promise at-most-once provider billing when a network call's outcome is unknown.

Index activation crosses primary and native databases. Cancellation after a native pointer change can leave an index requiring reconciliation even though the mode change is cancelled. `pending_index_recoveries` and `GET .../transitions/{id}/recoveries?limit=50` distinguish an active worker lease, required reconciliation and a resolved index. Inspect the current pointer and permitted actions; do not assume cancellation rolled it back.

Follow the recovery page's `next_cursor` using `after`; its page limit is not a corpus limit. Python exposes `knowledge_mode_recoveries`, TypeScript `knowledgeModes.recoveries`, and Java `knowledgeModes(tenantId).recoveries`. Each `KnowledgeModeRecoveryReceipt` retains an immutable `receipt_id`, attempt revision, original workspace/native index and model, plus a separately revisioned resolution. Reusing an index in another transition does not rewrite an earlier receipt. Archived workspaces and replaced bindings remain visible to an authorized administrator, with recovery actions disabled until the exact prerequisite is restored. Current permissions are required on every read and action.

Cancelling closes the parent authority without enumerating its children. The worker settles cancelled child jobs in batches of 25; the parent fence already prevents new provider/publication work while that cleanup finishes. A model call already in flight may still incur usage, but cannot publish under the cancelled authority. Pending activations remain separately recoverable and block another mode request.

Use the existing index activation endpoint with `IndexActivateInput`, the recovery receipt's current `expected_revision`, `expected_active_id`, `expected_connection_revision`, and a permitted `recovery` action. Python uses `activate_knowledge_index`, TypeScript `knowledgeIndexes.activate`, and Java `knowledgeIndexes(tenantId).activate`. `finish` only completes an already-applied target pointer; `restore_previous` reconciles the recorded previous pointer. Both require current index-write authority. Neither revives the cancelled mode transition or repeats embedding calls. If `actions` is empty, inspect the stated lease, pointer or authority prerequisite before proceeding. See [Knowledge indexes](knowledge-indexes.md).

## Verify answers after activation

After the transition succeeds, read the active settings revision. Start a new Chat operation over explicitly authorized documents with a known answer. Check the answer, cited source versions and parts, applied mode and policy revision. Test denied sources and missing evidence as well. Existing runs and retries retain their captured policy and are not acceptance evidence for a new revision.

RLM also requires its qualified secure execution runtime and supported model action protocol. A preparation receipt establishes its recorded prerequisites; it is not a live-provider answer evaluation. Record model identity, deployment, policy revision, run ID, latency, observed answer and unresolved errors separately.

MCP uses the same authorized services. `koinon_search` retrieves evidence with `answer=False`; a host composing an answer follows its own model workflow. `koinon_answer_audit` reads a permitted existing audit. There is no MCP administration tool for changing organization answer mode; use Settings or the authorized API/SDK. See [MCP knowledge workflows](../guides/mcp-knowledge-management.md).

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
