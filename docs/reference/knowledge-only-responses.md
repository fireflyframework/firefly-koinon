<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Knowledge-only responses

koinon answers from the knowledge the current user can access. It does not offer general chat or use the model's training knowledge as an additional factual source. A successful search alone does not make a model's next paragraph trustworthy.

## What an answer can contain

The model selects evidence for the current question. The server writes the final response using a fixed introduction, exact source quotations and verified dataset values. The model cannot supply an additional answer paragraph, an invented citation, a replacement value or a calculation coefficient. An unsupported selection rejects the whole proposed answer; koinon does not publish the valid half of a mixed response.

| Evidence | Eligible answer material |
| --- | --- |
| Published documents and curated knowledge | Exact text from the admitted extraction or immutable knowledge version, with the recorded source and revision |
| Governed dataset queries | Actual returned cells with native execution proof and supported column lineage; supported aggregates retain that lineage |
| Explicitly selected private files | Exact verified extracted text or chunks from the current authorized selection |
| Conversation history | Context for understanding the question; it does not supply facts for the new answer |
| Model analysis or general training knowledge | Ineligible |
| An image checksum without a verified text extraction | Ineligible |

SQL literals, unsupported expressions and model-authored RLM conclusions cannot be promoted into answer facts. Raw search, schema and query APIs remain useful for inspecting data. A raw query result is not a verified answer, even when it has executed successfully. The native RAG and RLM boundaries and supported SQL expressions are explained in [Curated RLM evidence](curated-rlm-evidence.md).

This response format deliberately preserves the distinction between a source excerpt and a new conclusion. A quotation establishes what the selected source says; it does not independently establish that every assertion inside a source is true or that the source is current. Inspect its recorded revision and availability in the audit.

For example, an ownership question can use an operations document that states who owns service reviews. A related financial question can use an accounting policy that records the dataset's currency and a governed sum over the invoices. koinon can present both exact passages and the calculated value together, retaining a separate source identity for each document and the dataset snapshot. It does not need to invent a connecting factual paragraph to make those results useful.

The mixed-source qualification covers two source files and invoice amounts of 1,250 and 2,750. A native DuckDB execution returns a sum of 4,000. The released calculation is labeled `SUM(orders.amount)` rather than accepting a model-authored alias as a factual claim. A synthetic sibling column does not become eligible simply because it appeared in the same successful query. This is source and execution qualification; a deployment's model connection and complete upload journey still require their own acceptance test.

## Streaming and publication

Tool activity can appear while the answer is being prepared. Model drafts, partial structured output, citations and answer cards remain private until the complete evidence selection passes validation. Current conversation scope, originating credential, selected sources and remembered context are checked again before publication.

One native database transaction stores the rendered text, answer policy, citations, selected cards and output receipt, then records the corresponding SSE events. If that transaction fails, it publishes neither a partial answer nor a partial receipt. Reconnecting to SSE uses the same sealed text rather than rerunning a draft. Text events from an earlier generation are not accepted as the current answer.

When evidence is insufficient, koinon returns a fixed explanation in the configured response language and asks the user to refine the question or select another source. Source access failures and unsupported RLM prerequisites have separate fixed explanations. A pending knowledge change remains a proposal requiring explicit user review; the response cannot approve or apply it.

## Read the output receipt

`AnswerAudit.output_release` is optional. Its absence means that no verified output release was recorded for that generation. It must not be inferred from an older `grounded` policy flag or from a complete retrieval manifest.

The receipt records the run, message and generation, policy version, publication sequence, selected fact identifiers, source references, result hashes, final text hash, citation hash, card hash and policy hash. The original retrieval records remain separate from this declaration of which facts were used in the published response.

Database migration `koinon_0039_answer_release` makes release rows append-only and permits at most one release for each run and generation. A refusal without a model generation is unique within its recorded reset context. A genuine retry creates a new context and can record another refusal without inventing a model call. Runtime updates, kind changes, deletes and cascading deletes cannot rewrite or remove a release. A retry appends its own generation while retaining earlier receipts. PostgreSQL also rejects truncation when release receipts exist.

These controls protect normal application operations and runtime database roles. They are not an external signature, a tamper-proof backup or a defense against a database owner changing the schema. Preserve the migration role separation and [backup and restore procedures](../operations/backup-restore.md).

## Earlier responses and saved transfers

Earlier unsealed responses keep their original database and audit records. Conversation views, SSE replay and new snapshots show a localized regeneration notice instead of treating that old prose as verified knowledge. Such responses do not contribute assistant text to new personal or project memory. Even a verified earlier response requires fresh source reads before its facts can answer another question.

Saved exports and shared conversations repeat the output check at their final transfer boundary. An older saved payload containing unsealed assistant prose cannot bypass the policy. Pending conversation-derived publication intents also retain an exact output capture from their preview; regenerating the conversation later cannot authorize the older pending text. Start a new preview when that capture is absent or no longer matches.

Previously published, explicitly confirmed knowledge versions retain their history. This policy does not silently delete or rewrite them. See [conversation memory](../guides/conversation-memory.md) for scope, project opt-in and revocation behavior.

## External MCP clients

koinon's tools enforce source permissions and return their recorded evidence. Claude, ChatGPT and other MCP clients control their own final prose and memory. Connecting a client to koinon does not make koinon authoritative over that client's model output. Configure the client to consult the repository and retain source provenance; use koinon's own answer and audit APIs when the server-enforced release policy is required.
