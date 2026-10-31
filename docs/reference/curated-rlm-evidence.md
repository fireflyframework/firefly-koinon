<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Curated RLM evidence

The source implementation can construct bounded RLM views from acknowledged, published knowledge versions. It retains a separate identity for each curated item and its supporting evidence. The organization capability remains `rlm_curated_knowledge_supported: false` with reason `KNOWLEDGE_RLM_UNQUALIFIED` until the installed runtime and real-model journey are qualified. A typed success shape or a passing local fixture does not enable that capability.

## Select a published version

Admission pins the canonical item, its canonical workspace, native item and workspace, published version identifier and number, and acknowledged commit operation. A newer draft does not replace the serving published version. The native version must retain its content and evidence hashes and its committed author and timestamp.

The managed reader checks current access to the item and its referenced evidence roots. It reads policy through a fresh primary transaction rather than relying on cached membership in an enclosing transaction. After the awaited checks, one bounded primary-database observation compares the complete selected authority material and effective expiry. That statement is the authorization cut for release. Native immutable version and commit proofs remain exact pins; this is not an atomic transaction across independent databases.

Changing the selected version, withdrawing serving status, revoking a source root, or changing relevant membership or credential authority prevents release. This applies to the whole selected set, including an earlier item revoked while a later item is being checked. Tenant and workspace boundaries remain authoritative in metadata, model context, execution callbacks and final evidence verification.

## Verify the complete view

A curated view contains the complete ordered body, not an arbitrary search passage presented as the whole version. Its manifest records:

| Material | Recorded identity |
| --- | --- |
| Serving knowledge | Canonical and native item/workspace identifiers, version identifier and number, acknowledged operation |
| Version metadata | Title, kind, domain, tags, committed author and timestamp |
| Version hashes | Content, supporting evidence and complete body SHA-256 |
| Ordered body parts | Stable part identifier, ordinal, character range and exact UTF-8 SHA-256 |
| Read context | The actual engine, database, catalog and schema when supplied by the native read |

The complete body is bounded to 256 KiB. Parts follow the canonical 4,800-character projection with deterministic version-bound identifiers. Validation rejects missing, reordered, duplicate, truncated or altered parts and mismatched byte lengths or body hashes. The manifest hashes the exact version metadata and ordered part identities. Part ordinals and character ranges are not document pages.

The operation owns its view and execution lease. A cancelled or completed operation cannot release a delayed read into a later request. A document and a curated item may coexist in the corpus without sharing an identifier namespace or an authority decision. Unsupported filters do not silently broaden the selection.

## Distinguish observation from use

| Native-read stage | What it establishes |
| --- | --- |
| `rlm.corpus` | Metadata admitted for this invocation |
| `rlm.root`, `rlm.submodel`, `rlm.forced_final`, `rlm.selector` | The prepared model-context fingerprint for the admitted scope |
| `rlm.knowledge_view.v1` | The exact complete curated-view manifest |
| `rlm.read` | The recorded complete body hash |
| `rlm.execution_read.v1` | Body bytes released to actual analysis execution |

Metadata discovery, an available view or citation lookup cannot credit a body as used by execution. A curated citation must resolve to the exact admitted version and verified part, including its content and part hashes. It does not receive a guessed document source version, extraction, page or recorded-loader coordinate. Its original supporting evidence remains attached to the immutable knowledge version.

A mixed answer must verify both domains. Valid document evidence cannot hide invalid curated evidence, and the reverse is also true. Final release reauthorizes the complete selected set after other awaited work. Audits retain recorded facts and hashes; they do not publish hidden model reasoning or reconstruct missing historical proof from current data.

## Read the SDK receipts

Python, TypeScript and Java expose the additive `RlmToolReceipt.knowledge_item_ids` field as a typed collection of strings. Java uses the accessor `knowledgeItemIds()`. The existing `source_ids` field continues to identify document sources. A knowledge identifier cannot be supplied in the document collection to satisfy a scope check.

Each collection defaults to empty where the language model applies defaults; an older wire receipt may omit the new field. TypeScript callers handle the optional field as an empty collection when absent. Java retains the previous constructor and normalizes absent collections to immutable empty lists. Python validates the native wire constraints: identifiers contain 1–64 characters, each domain is unique, and the combined scope is nonempty and bounded to 500 identifiers. The server remains authoritative for scope admission in every language.

The collections identify the admitted scope of a recorded tool action. They do not replace the exact source/version/part proof in `AnswerAudit.sources` or the actual-use records in `AnswerAudit.native_reads`. Where function-tool traces are recorded, `AnswerAudit.rlm_tools` links actions to request, schema, argument, result and execution hashes. An absent historical trace remains absent.

## Keep publication separate

An RLM answer does not create or publish a knowledge version. A derived conclusion still requires the user's explicit authorization for the exact content, destination and supporting versions. `CURATED_DERIVATION_UNQUALIFIED` remains in force for unsupported derivation paths. Selecting RLM, granting a read scope or completing a model run cannot supply publication consent.

Before enabling curated RLM in a deployment, qualify the installed artifacts with the configured model and real acknowledged knowledge. Cover knowledge-only and mixed inputs, current-scope revocation, exact historical replay, cancellation, citation correctness and the unchanged consent boundary. Keep the capability disabled until that evidence is complete. Read [organization knowledge behavior](../operations/organization-knowledge.md) for model assignment and policy configuration.
