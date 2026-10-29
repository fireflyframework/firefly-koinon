<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Organization knowledge behavior

Organization administrators configure document answer behavior and structured-query parameters in **Settings → Knowledge models**. The Knowledge behavior panel applies to the selected organization. Model assignments beneath it may have a workspace scope; workspace assignment rights do not grant permission to change organization behavior.

Read the current values and server capabilities before editing. With no saved organization policy, revision `0` and origin `deployment` identify the validated deployment values. Saving the complete policy creates an organization revision. There is no implicit switch from RAG to RLM. Inherited document `answer_top_k` preserves the canonical baseline of `10`.

## Save and review

1. Select the intended organization and read its current policy.
2. Choose document RAG or RLM and review the required model assignment. Open advanced controls only when their defaults need changing.
3. Review the server-provided numeric bounds and capability reasons. Save sends both complete document and structured settings with the revision that was read.
4. If another administrator saved first, reload the current policy and review the differences. SDKs do not automatically retry configuration writes.

`GET /api/v1/tenants/{tenant_id}/knowledge/settings` is available to an authorized caller in that organization with knowledge search, query execution, chat use, or organization settings-write permission. `PUT` requires organization-level `settings:write`. Neither operation accepts workspace filters. Current membership and credential bounds remain authoritative.

The input is a strict `OrganizationKnowledgeSettingsInput`: `expected_revision`, `documents`, and `structured`. All nested policy fields are required. Unknown fields, unsupported modes, nonfinite confidence, and booleans supplied as integers are rejected. Read-only capabilities are returned with the current settings and are not part of the update body.

## Document answers

RAG uses authorized document retrieval and the configured answer model. RLM selects the native iterative answer engine and its bounded analysis/subcall behavior. The writable `documents.rlm` assignment supplies that model connection; deployment observations do not create separate writable root/submodel controls. A missing or incompatible assignment fails explicitly.

RLM over curated knowledge remains unqualified. The server returns `rlm_curated_knowledge_supported: false` and reason `KNOWLEDGE_RLM_UNQUALIFIED`; callers must preserve that limitation rather than silently fall back to another engine. Selecting an engine does not grant access to more content.

RLM also requires recorded immutable document views. Capabilities expose `rlm_recorded_views_required: true` and reason `RLM_DOCUMENT_VIEWS_REQUIRED`. This is a prerequisite, not an availability observation. A run whose authorized documents lack those views fails explicitly; it does not infer historical provenance or silently switch to RAG.

| Document parameter | Accepted values |
| --- | --- |
| `answer_mode` | `rag` or `rlm` |
| `retrieval_top_k` | 1–200 |
| `retrieval_per_query_k` | 1–500 |
| `retrieval_rrf_k` | 1–1000 |
| `query_expansion_enabled` | boolean |
| `query_expansion_n` | 1–10 |
| `answer_top_k` | 1–40 |
| `rlm_max_iters` | 1–64 |
| `rlm_sub_budget` | 0–128 |
| `rlm_max_depth` | 0–8 |
| `rlm_self_consistency` | 1–8 |
| `rlm_extended_reasoning` | boolean |

## Structured queries

These options configure the real request-local query pipeline. They do not enable direct SQL, change the SQL firewall, or authorize derived-knowledge publication.

| Structured parameter | Accepted values |
| --- | --- |
| `top_k_schema` | 1–100 |
| `top_k_examples` | 0–50 |
| `top_k_metrics` | 0–50 |
| `rrf_k` | 1–1000 |
| `generation_candidates` | 1–8 |
| `max_refine_retries` | 0–8 |
| `grounding_min_confidence` | finite number from 0 through 1 |

Use the typed bounds returned in `capabilities.documents.bounds` and `capabilities.structured.bounds` as the authoritative control limits. Deployment restrictions still apply. Credentials, storage/index backends, sandbox controls, SQL admission, consent, and auto-learning authority are outside this policy.

## SDKs and applied policy

Python exposes `organization_knowledge_settings` and `update_organization_knowledge_settings`:

```python
from koinon_sdk import DocumentKnowledgeSettings, OrganizationKnowledgeSettingsInput

current = await client.organization_knowledge_settings(tenant_id)
change = OrganizationKnowledgeSettingsInput(
    expected_revision=current.revision,
    documents=DocumentKnowledgeSettings.model_validate({
        **current.documents.model_dump(), "answer_mode": "rag",
    }),
    structured=current.structured,
)
updated = await client.update_organization_knowledge_settings(tenant_id, change)
```

TypeScript exposes the same policy through `organizationKnowledge.get/update`:

```ts
const current = await client.organizationKnowledge.get(tenantId);
const updated = await client.organizationKnowledge.update(tenantId, {
  expected_revision: current.revision,
  documents: {...current.documents, answer_mode: 'rag'},
  structured: current.structured,
});
```

Java provides `client.organizationKnowledge(tenantId).get()` and typed synchronous/asynchronous `update` methods:

```java
var current = client.organizationKnowledge(tenantId).get();
var change = OrganizationKnowledgeSettingsInput.empty()
    .withExpectedRevision(current.revision())
    .withDocuments(current.documents().withAnswerMode(KnowledgeAnswerMode.RAG))
    .withStructured(current.structured());
var updated = client.organizationKnowledge(tenantId).update(change);
```

New durable chat runs retain the full immutable `OrganizationKnowledgeSnapshot` admitted for that run. Workers and retries use that captured policy after later administrator edits. Direct search/query responses and answer audits expose optional `knowledge_settings_snapshot` metadata containing the schema version, organization revision, origin, policy, and digest. Missing historical metadata stays null or absent; do not reconstruct it from today's settings. The server owns digest validation and policy authorization.

Saving behavior does not create or approve knowledge content. Source, package, hosted CI, deployed engine behavior, and external-provider qualification are separate checks; see the [qualification record](qualification.md). A configured connection is not evidence that an external provider has been exercised.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
