<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Switch document answers between RAG and RLM

Open **Settings** and select **Knowledge answers** to change document answer behavior for the selected **organization**. It is not a file conversion, a workspace preference or an upload option. RAG retrieves passages before generating an answer. RLM analyzes recorded document views through bounded model actions. Neither choice changes permissions, publishes knowledge or converts a spreadsheet into a document.

New operations use the effective organization policy. A durable chat run captures its complete policy revision when admitted; its worker and retries retain that snapshot after an administrator changes the organization. Switching back does not rewrite an existing run or its audit. Start a new run to test a new policy.

## 1. Record the current state

Select the intended organization and read its current revision, origin, document settings, structured settings and capability reasons. Revision `0` with origin `deployment` means no organization override has been saved. Changing the policy requires organization-level `settings:write`; workspace model-assignment authority alone is insufficient.

Record the affected workspaces and a small set of authorized documents with known answers. Keep the current policy and model assignments for a reviewed rollback. Do not include provider credentials or document bodies in the change record.

## 2. Check the intended engine

| Check | RAG | RLM |
| --- | --- | --- |
| Model | Verify the effective document answer assignment and any configured fallback/consolidation roles. | Verify the effective `documents.rlm` assignment and the exact model's supported action protocol. |
| Content | Confirm ingestion is complete and retrieval returns the intended source evidence. | Confirm every selected document has its recorded immutable version and extraction view. Missing views fail with `RLM_DOCUMENT_VIEWS_REQUIRED`. |
| Index | Inspect the active document embedding target when dense retrieval is required. | Switching modes does not itself require an embedding rebuild; document view and model prerequisites still apply. |
| Curated knowledge | Use its governed retrieval path. | Curated RLM remains unsupported: `rlm_curated_knowledge_supported: false`, with `KNOWLEDGE_RLM_UNQUALIFIED`. |
| Execution | Test retrieval and the generated answer separately. | Require the supported secure execution runtime and an actual model test with exact evidence. Missing required execution support fails with `RLM_SECURE_EXECUTION_REQUIRED`. |

**Model assignments** has organization defaults and workspace overrides. Inspect the effective assignment in every affected workspace: a disabled override blocks fallback instead of inheriting the organization default. The Knowledge answers prerequisites panel reports organization assignment observations, not complete workspace readiness. An enabled assignment is not proof of provider availability, supported model behavior or successful answers.

Saving an otherwise valid RLM policy does **not** preflight every workspace model or document view. An administrator can save RLM while prerequisites are missing; execution then fails explicitly. Keep RAG selected until the intended RLM model, views and representative answers have been qualified. There is no silent RLM-to-RAG repair when a model, action protocol, permission or evidence requirement fails.

Use a separate test organization when qualification must occur before changing production organization defaults. Within an organization, selecting one test workspace does not make the policy change workspace-local.

### When an index change is needed

Changing only the answer engine does not rebuild an index. Changing the embedding model, dimensions or embedding space can require a new compatible target. Follow [Build and activate a knowledge index](knowledge-indexes.md): inspect the actual active target, review a plan, submit a durable build once, wait for coverage and physical-index qualification, then perform the separate activation review using current revisions. A queued build is not a ready target, and a ready managed record is not proof that its native pointer is active.

Without an active document embedding set, the native retrieval service can use lexical retrieval with its dense half disabled. Do not report that as a successful dense-vector check. Changing dataset embeddings is a separate lifecycle. The [configuration change procedure](../guides/configuration-lifecycle.md) covers provider and assignment rollback as well as index activation.

## 3. Save one complete policy

In **Knowledge answers**, choose the engine, review the displayed capabilities and bounds, then save. The request includes the complete document and structured policies and the revision read earlier. Preserve unrelated settings. On a revision conflict, reload and review the current policy; do not replay a stale write automatically.

The canonical API is `GET` and `PUT /api/v1/tenants/{tenant_id}/knowledge/settings`. It does not accept a workspace selector. The input is `OrganizationKnowledgeSettingsInput`, containing `expected_revision`, `documents` and `structured`; capabilities are read-only response fields.

With an authenticated Python SDK client and an authorized `tenant_id`:

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
updated = await client.update_organization_knowledge_settings(tenant_id, change)
```

The equivalent TypeScript operation preserves both policy sections:

```ts
const current = await client.organizationKnowledge.get(tenantId);
const updated = await client.organizationKnowledge.update(tenantId, {
  expected_revision: current.revision,
  documents: {...current.documents, answer_mode: 'rlm'},
  structured: current.structured,
});
```

Use `rag` instead of `rlm` for a reviewed switch back. Java exposes `client.organizationKnowledge(tenantId).get()` and typed `update(...)` methods. See [Organization knowledge behavior](organization-knowledge.md) for the Java example, complete parameter bounds and policy provenance, and [Headless API and SDK](../guides/headless.md) for client setup and authentication. The examples change policy; they do not validate a provider or migrate content.

For complete programs with imports, authentication, client lifecycle and reviewed write helpers, use the [Python tutorial](../examples/python/README.md) and [administration source](../examples/python/administration.py), the [TypeScript tutorial](../examples/typescript/README.md) and [administration source](../examples/typescript/administration.mts), or the [Java tutorial](../examples/java/README.md) and [administration source](../examples/java/JavaAdministration.java). Their write helpers receive the policy revision already reviewed by the operator; they do not silently replace it with a later revision.

## 4. Verify a new run and its evidence

1. Read the saved policy back and record the returned revision and origin.
2. Start a **new** chat run with an explicit authorized scope and a question whose answer is known. Repeat in workspaces with distinct overrides.
3. Inspect the answer audit's recorded mode, organization revision and policy origin. Verify cited source versions and parts against the expected answer. For RLM, distinguish document metadata observations from actual execution-use evidence.
4. Test missing evidence and a denied source. These must not become a fabricated answer, an expanded scope or a silent engine switch.
5. Observe a previously queued run or retry: its captured policy must remain unchanged. Do not use its result as acceptance of the newly saved revision.

Record the deployment, actor, scope, model identity, policy revision, run ID, observed result and unresolved failures. Latency, cost and answer correctness are separate observations. A passing local test, a provider capability label or a tool receipt alone does not establish deployed model acceptance.

The existing MCP tools use the canonical authorized services. In particular, `koinon_search` retrieves evidence with `answer=False`; it does not generate an organization RAG/RLM answer. A host assistant composing an answer from that evidence follows its own model workflow. `koinon_answer_audit` reads an existing permitted audit. There is no MCP administration tool for changing this organization policy; use Settings or the authorized API/SDK. See [MCP knowledge workflows](../guides/mcp-knowledge-management.md).

## 5. Recover deliberately

| Observation | Action |
| --- | --- |
| Revision conflict | Reload the current policy and review the complete replacement before saving. |
| Missing or incompatible model binding | Inspect effective organization/default and workspace override assignments; qualify the intended model. |
| Missing recorded views | Inspect ingestion and lineage for the selected sources. A policy save does not backfill views or historical provenance. |
| Unsupported curated RLM scope | Use a supported document scope or explicitly restore RAG for new operations. Do not hide the unsupported result. |
| New RLM runs fail after switching | Restore the reviewed RAG policy with the **current** revision, verify a new run, and inspect existing runs separately. |
| Broad scope is rejected | Narrow the current question's scope. Do not silently select a subset and present it as a complete corpus answer. |

For input-size costs, per-call limits and measurement guidance, see [Knowledge scaling](../concepts/knowledge-scaling.md). Keep [qualification evidence](qualification.md) separate from publication and live-provider acceptance.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
