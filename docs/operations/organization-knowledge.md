<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Organization knowledge behavior

Organization administrators configure document answer behavior and structured-query parameters by opening **Settings** and selecting **Knowledge models**. The Knowledge behavior panel applies to the selected organization. Model assignments beneath it may have a workspace scope; workspace assignment rights do not grant permission to change organization behavior.

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

An RLM answer does not publish new knowledge. Any proposed repository change needs a separate review of the exact content, destination and source versions, followed by the user's explicit approval. A model-generated conclusion or a successful analysis run cannot supply that approval.

Curated support requires the exact acknowledged published version and its complete ordered content, current access to its source roots, and citations that identify the knowledge version. Original document citations cannot stand in for a curated version's body. Keep the capability disabled until those reads, permissions and completion evidence are qualified together. The source implementation provides a separate typed curated-version reader and receipt path; this does not change the advertised capability or establish real-model acceptance. [Curated RLM evidence](../reference/curated-rlm-evidence.md) describes its version, scope and audit contracts.

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

### Model connection and execution

RLM borrows the admitted `documents.rlm` connection, including its model, output mode and bounded model settings. An Ollama connection with native output uses a strict JSON Python action, validated before execution. A default-output connection retains function-tool calling. The protocol is selected before the first request; an invalid response does not switch models, protocols or answer modes.

Required analysis uses persistent Monty sessions through the public execution API in pyfly. The current runtime requirement is pyfly 26.10.24 or later within the supported release range. Only fixed document and model helpers cross the host boundary; host objects, filesystem access and network access are unavailable to analysis code. Missing runtime support or a legacy execution override fails with `RLM_SECURE_EXECUTION_REQUIRED` before model dispatch. Restricted CPython builtins and a scrubbed subprocess environment are insufficient isolation; those legacy modes are available only through explicit standalone configuration.

Default-output RLM offers `python` for inspection and computation and `final_answer` for answer text and citation identifiers. The terminal tool carries text as data, including quotes and line breaks. A fixed orchestrator feed invokes the same final validator and real VM halt used by the guest `final(...)` helper. It cannot bypass source reads, current access checks or execution budgets. A terminal call must be the only tool call in its response; reused call identifiers are rejected. Native JSON continues to use its existing Python action protocol.

Each analysis candidate and its descendants share a cooperative 300-second lifetime and callback admission budget. VM memory is limited to 64 MiB; the configured compute/request timeout defaults to 30 seconds and accepts 1–120 seconds. Session limits also bound feeds, suspensions, captured output and data crossing the host boundary. Trusted callbacks enforce their own I/O deadlines: the lifetime check does not forcibly interrupt a running callback. A rejected final drains with further host callbacks denied; a valid final halts without resuming analysis code. Terminal or uncertain cleanup cannot create a replacement session or authorize replay.

The secure guest interface exposes `docs.keys()`, `docs.get(id)`, `docs.pages(id)`, `docs.npages(id)` and `docs.contains(id)`. It uses Monty's supported Python subset, including native regular expressions. It does not implement a full host Python interpreter or lazy mapping operators; submitted code is never rewritten to make it succeed.

Installed-runtime and source checks are separate from real-model acceptance. Keep RAG enabled until the selected model has demonstrated correct answers with exact source evidence; valid action syntax, a successful document read or a negative conclusion alone does not establish answer correctness.

Invalid actions consume the existing iteration limit. Native JSON exhaustion stops the engine without an unrestricted final-answer request. Text subcalls remain secondary assistance and cannot replace the original source evidence. `rlm_extended_reasoning` controls the analysis workflow; it does not establish that a provider's thinking mode can be disabled. Check the exact model's supported settings rather than inferring them from a general capability label.

When self-consistency is enabled, a required candidate's execution failure fails the request rather than becoming an absence-of-knowledge response. Selection runs on an authorized worker, rechecks current access and requires one valid candidate number. Model, permission and selection-protocol failures cannot silently choose the first candidate.

Request provenance fingerprints the effective instructions, SDK history, prepared tool or output schema and model-settings identity before dispatch. Default-output RLM also records actual function actions in the optional `AnswerAudit.rlm_tools` collection. Each entry links the provider call identifier, tool name, prepared request and schema hashes, canonical SDK argument/result hashes, public VM-feed hash and actual execution outcome. The canonical hashes use sorted keys, compact JSON and UTF-8. The SDK result hash includes the actual `ToolReturnPart` serialization; its instance is preserved into subsequent request history. `accepted_final` and `execution_failure` entries seal the actual host result locally and do not claim delivery in a later provider request.

Tool receipts share the existing capture byte envelope and have separate bounded action allowances. SQL attempt limits retain their SQL-only meaning. A null collection means no tool trace was recorded; historical conversations are never backfilled. Recorded entries do not assert that an interrupted generation has a complete trace. Receipts contain hashes rather than model reasoning, source bodies or readable Python code; a readable code expansion is not currently provided in the audit UI.

Document content released to analysis code has separate, versioned execution-use evidence. Metadata lookups, page counts and citation resolution cannot credit a document as used. Every cited document view must have an exact execution-use record; answer sources and hits exclude views loaded only for metadata. Those observations remain in the audit. Read and permission checks, immutable part verification and capture budgets still apply before content release.

Execution-use evidence belongs to the answer invocation, which can include self-consistency candidates; it does not identify an individual provider call or candidate. Historical read records without this marker establish recorded observations, not confirmed execution use. Do not backfill that distinction from current content.

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

New durable chat runs retain the full immutable `OrganizationKnowledgeSnapshot` admitted for that run. Workers and retries use that captured policy after later administrator edits. Direct search/query responses and answer audits expose optional `knowledge_settings_snapshot` metadata containing the schema version, organization revision, origin, policy, and digest. The audit overview displays the recorded mode, organization revision and policy origin. Document source details also expose recorded part SHA-256 values. Missing historical metadata stays null or absent; do not reconstruct it from today's settings. The server owns digest validation and policy authorization.

Saving behavior does not create or approve knowledge content. Source, package, hosted CI, deployed engine behavior, and external-provider qualification are separate checks; see the [qualification record](qualification.md). A configured connection is not evidence that an external provider has been exercised.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
