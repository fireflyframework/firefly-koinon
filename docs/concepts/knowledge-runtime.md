<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Agents, embeddings and knowledge engines

koinon connects a question to the knowledge its caller can access. Documents, datasets and reviewed knowledge have different processing paths, but share organization boundaries, source identities and answer audit. The interface, embedded components, SDKs and MCP use the same authorized services.

## What each component does

| Component | Responsibility | Configuration |
| --- | --- | --- |
| Model provider | Supplies a particular model through an approved endpoint and API protocol. | **Providers** |
| Chat agent | Combines a model, instructions, allowed tools and a permitted knowledge scope. | **Agents** |
| Knowledge model assignment | Selects the model used for a processing role, such as embeddings or SQL generation. | **Knowledge models** |
| Embedding model | Converts content and search input into compatible vectors for retrieval. It does not write an answer. | An explicit embedding assignment, dimensions and embedding space |
| Retrieval index | Makes the recorded knowledge searchable using the configured retrieval backend. | **Storage & indexing** and deployment configuration |
| Answer policy | Chooses document RAG or RLM and bounds retrieval, analysis and structured-query work. | **Knowledge behavior** within **Knowledge models** |
| Conversation worker | Executes a durable admitted run, retains events and evidence, and observes cancellation and lease ownership. | Deployment configuration |

A connected provider, a discovered model and a successful capability check are different observations. Check the exact model's chat, streaming, tool and image support. A saved connection does not establish that an end-to-end answer has been tested.

## Choose the knowledge path

| Need | Path | Evidence to inspect |
| --- | --- | --- |
| Find and summarize relevant document passages | Retrieval-augmented generation, or **RAG** | Retrieved passages and their immutable document versions, extractions and parts |
| Inspect recorded document views through bounded iterative analysis | The recursive language model, or **RLM**, document engine | Execution-use records, source parts, analysis outcomes and final citations |
| Calculate from tables | Structured question grounding, SQL generation and governed execution | Executed SQL, database context, dataset and table snapshots, returned values |
| Supply a file to one conversation | Private attachment processing | The selected attachment, extraction state, retention and recorded private-file evidence |

These are explicit paths. A private attachment is not published Library knowledge, a document spreadsheet extraction is not a queryable dataset, and selecting RLM does not silently fall back to RAG. See [intake modes and formats](../guides/intake-formats.md) before importing a file.

## How document RAG works

The service validates the requested scope and current access before retrieval. Its configured retrieval settings bound the candidates, per-query results and final answer context. Query expansion can add search formulations when enabled; reciprocal rank fusion combines retrieval rankings. More candidates can increase cost and irrelevant context, so tune against representative questions rather than maximizing every limit.

Retrieved content must bind to its recorded document version, extraction and source part before it reaches the answer model. An older answer keeps those recorded identities after replacement of the current document. Missing historical evidence cannot be reconstructed from today's document. [Versions and lineage](../guides/lineage.md) explains these identities and the authenticated historical-read APIs.

The answer model receives the admitted context and prepares the response. Retrieval rank measures relevance; it is not a confidence score or an access decision. Review the cited passages when assessing whether an answer follows from its evidence.

## How embeddings and indexes fit together

Document and structured retrieval have separate embedding assignments. Embedding configuration includes the provider, model, dimensions, storage dimensions where applicable, and a compatible existing embedding space. Generative model roles cannot substitute for an embedding assignment. The two sides of a similarity search must use compatible embeddings.

Changing the model or dimensions can make an existing index incompatible. Removing and recreating an assignment does not authorize reuse of an incompatible space. Plan and qualify reindexing before switching indexed knowledge to a different embedding configuration. Storage readiness, index readiness and successful retrieval must each be checked.

Organization defaults and workspace overrides are distinct. A disabled explicit workspace override blocks fallback to the organization default. The server's role descriptors determine which generative roles may borrow the current agent; do not infer this from a model's name. Embedding roles require an explicit connection.

The current processing-role catalog is:

| Role | Purpose |
| --- | --- |
| `documents.answer` | Document answers and query expansion |
| `documents.fallback` | Explicit document-answer fallback; it does not switch an RLM run to RAG |
| `documents.consolidation` | Document consolidation during ingestion |
| `documents.rlm` | Bounded document analysis and evidence tools |
| `documents.embedding` | Document embeddings |
| `structured.grounding` | Ground a question against structured knowledge |
| `structured.generation` | Generate a dataset query |
| `structured.critic` | Review and repair a generated query |
| `structured.explainer` | Explain returned results |
| `structured.describe` | Schema descriptions and names during ingestion |
| `structured.relation_proposal` | Propose structured relationships |
| `structured.rename_detection` | Detect schema renames |
| `structured.embedding` | Structured-schema embeddings |

Read the returned descriptors and setup state before assigning a role. An assignment is configuration; it does not establish that every workflow using that role is qualified. The [qualification record](../operations/qualification.md) identifies the tested boundaries.

## How RLM differs

RLM uses iterative analysis over recorded document views, with limits on iterations, subcalls, depth, self-consistency and execution resources. It borrows the admitted `documents.rlm` connection. Actions must match the selected protocol and pass validation before execution; a protocol error does not authorize a model or engine switch.

Secure execution uses the framework's persistent Monty session API. Analysis code receives fixed document and model helpers rather than host filesystem, network or unrestricted Python access. Document metadata lookups and actual content use have separate evidence: knowing that a document exists is not proof that its contents were read.

Recorded views are required. Curated-knowledge RLM is currently unqualified and advertised as unsupported through `KNOWLEDGE_RLM_UNQUALIFIED`. Curated inputs have their own exact-version evidence contract; they do not borrow document page numbers or source identities. See [curated RLM evidence](../reference/curated-rlm-evidence.md) for the source implementation and remaining qualification boundary. Do not enable a custom fallback or treat an original document citation as a citation to a curated version. The full [organization knowledge policy](../operations/organization-knowledge.md) documents prerequisites, action protocols, budgets, execution-use evidence and current limitations.

Test the chosen model with a question whose expected answer and exact source parts are known. Valid action syntax, an executed read or a negative conclusion alone does not establish answer correctness. An installed runtime or a local model test also does not qualify every deployed provider and model.

## Structured questions and agent tools

An agent may be allowed to search knowledge, inspect dataset schemas and query datasets. Each tool checks the caller's current authority and admitted scope. Agent instructions and organizational positions cannot grant additional access. The organization chooses the default chat agent centrally; end users choose their question and relevant knowledge, not a different security policy.

The structured pipeline has separate roles for grounding, SQL generation, repair and explanation, with additional ingestion roles advertised by the server. Query policy bounds candidates and refinements. Generated SQL still passes the execution firewall and executes against authorized registered data. An imported snapshot queried through DuckDB retains a different identity from the original file, workbook section or recorded origin database.

Do not display schemas and execution diagnostics as extra answer cards. The primary answer and its useful result belong in the conversation; **Audit** holds the recorded SQL, source lineage, tool activity and coverage. OpenUI resolves registered components against stored evidence within the run. A model response cannot supply arbitrary executable HTML or fetch destinations.

## Memory, provenance and knowledge changes

Conversation history is durable, owner-scoped and reauthorized before reuse. Narrowing a question cannot carry broader evidence into its model context. Closing an SSE stream releases its connection; explicitly cancel the run to stop generation. Consumers must handle reset, failure, cancellation and completion events. See [agents and chat](../guides/agents.md) and the language-specific SDK conversation guides.

Each new durable run captures the effective organization knowledge policy. Later settings changes do not relabel that run. Audit records observable tools, requests, outcomes and source-use evidence; it does not expose hidden model reasoning or invent a confidence score. Unrecorded historical fields remain unknown.

An answer or derived conclusion is not automatically published knowledge. Review the exact proposed content, destination and source versions, obtain the user's explicit authorization, then apply the corresponding write. Directly authorized API maintenance also requires current roles, scopes and revision checks. The SDKs never silently approve a proposal or retry an uncertain write.

Start with the [guided configuration path](../guides/knowledge-setup.md). Use the [qualification record](../operations/qualification.md) to distinguish implemented contracts, source tests, installed-package checks, real-model observations and deployed acceptance.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
