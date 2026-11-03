<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# RAG and RLM performance study

Choosing an answer technique affects where the system spends its time. RAG retrieves a limited set of passages before generation. RLM gives an execution session access to recorded document views and lets it inspect relevant content over several steps. Both require current permissions, immutable source identities and evidence validation.

Neither technique has one useful complexity label for the entire request. A fast vector lookup can sit behind a slow permission pass. A short RLM conversation can read a large document repeatedly. This study separates those stages, reports measurements where available and explains how to qualify a larger installation.

## What the measurements establish

The study has three independent workloads. They must not be added together as though they were one instrumented chat request.

| Workload | Real components exercised | Boundary |
| --- | --- | --- |
| Selected source metadata | Native repository, SQLAlchemy, SQLite and RLM corpus builder; 100 to 10,000 selected rows | No product permission pass, immutable version pinning, document content or model execution |
| Authorization batches | Product permissions, repositories, native ID projection and fresh authority snapshots; SQLite and PostgreSQL | Measures SQL statements and revocation behavior, not answer latency |
| Native answers with Azure models | Native document ingestion, PostgreSQL 17, pgvector 0.8.7, embeddings, hybrid retrieval, RLM execution and source verification | Two documents and one request at a time; controlled authorization and policy fixtures, not authenticated chat load |

Results below were collected on November 3, 2026 UTC. Native answer observations use released `26.11.10` and the source change in [retrieval reuse PR 117](https://github.com/fireflyframework/firefly-koinon/pull/117). Metadata observations use source revision `f113e6e9dafff6c6d567dffe571a0b7dd5aead8d` with pyfly `26.11.5`. Authorization observations belong to [batch admission PR 115](https://github.com/fireflyframework/firefly-koinon/pull/115). A source comparison does not mean an existing installation already runs those changes.

Both actual-provider comparison runs used pyfly `26.10.32`. Hosted integration checks also passed with `26.11.5`, but those checks are not an additional live-provider performance measurement.

## Choose a technique for the question

For questions answered by a few relevant passages, start by evaluating RAG recall and citation quality. Its candidate window limits the material sent to generation, although permission checks and database traversal still have their own costs.

For questions requiring inspection across sections or whole documents, evaluate RLM's actual reading pattern and model calls. Its advantage is flexible access to recorded content, not a guarantee that it reads less or answers faster. A broad scan can be substantially more expensive than passage retrieval.

For totals, joins and aggregations over structured datasets, measure the governed SQL path as well. A correct model calculation is insufficient when the final answer requires a recorded derived-value proof. Existing capability and evidence guards take precedence over a technique preference.

There is no overall winner established by the two-document comparison. Choose using representative questions, verified final answers, retrieval quality and resource measurements on the target installation. Use the [switching guide](../operations/rag-rlm-switching.md) to understand what preparation the selected mode needs.

## Understand the work before comparing times

Use these input dimensions when planning capacity:

- **Stored corpus:** total sources, chunks, vector dimensions and stored object sizes.
- **Authorized selection:** sources and workspaces available for this particular operation under current permissions.
- **Content touched:** original, expanded, normalized and text sizes actually processed. A compressed presentation or spreadsheet can expand substantially.
- **Question workload:** query variants, candidate passages, RLM actions, nested calls and model tokens.
- **Concurrency:** admitted requests, queued requests, parser children, database connections and provider quotas.

For the formulas below, `A` is selected sources, `C` is eligible chunks, `D` is vector dimensions, `B` is bytes processed, `M` is lexical matches, `V` is vector candidates visited, `Q` is query variants, `p` is candidates per variant and `U` is distinct fused candidates. These variables are independent; doubling uploaded files does not necessarily double all of them.

### Shared ingestion and preparation

| Stage | Work that grows | What to measure |
| --- | --- | --- |
| Receive, hash and persist an original | Reading and hashing all original bytes requires `O(B)` work. Streaming can bound the transfer buffer; it does not bound later parsing memory. | Transfer time, throughput, object operations, original size and peak transfer buffer |
| Extract DOCX, XLSX, PPTX, PDF or multimodal content | Depends on expanded bytes, cells, slides, pages, embedded objects and OCR or model calls. A file-size-only complexity claim is insufficient. | Parser wall and CPU time, child-process RSS, scratch high-water mark, expanded size, timeout and rejection reason |
| Normalize and chunk | At least proportional to text inspected; chunk overlap and repeated transformations add work. | Normalized size, text size, part count, chunk count and CPU time |
| Embed and build an index | Provider work depends on submitted tokens and batches; vector storage grows with chunk count and dimensions. ANN construction also depends on graph parameters and data. | Embedding tokens, batch count, throttles, index build duration, index size and completed coverage |
| Prepare RLM views | Recorded extraction and versioned views are still required. Avoiding query embeddings does not make ingestion free. | Missing-view count, source/version checks, bytes re-extracted and persisted view size |

For illustration, 100,000 vectors with 1,536 float32 components contain about **586 MiB of component data alone** (`100000 × 1536 × 4`). This is arithmetic, not a measured database footprint: row metadata, text, indexes, object copies and temporary build space are additional. It is not a worker-memory recommendation.

### Shared authority and source preparation

Batching reduces SQL statement count, but the application must still examine admitted identities and enforce authority. The selected native metadata path issues `ceil(A / 200)` reads, prepares filter sets once and globally sorts rows in `O(A log A)` work. It retains `O(A)` metadata. Immutable product version pinning adds work for every admitted source and is excluded from the metadata-only benchmark below.

Current product authorization still has catalog enumeration work. A handful of SQL statements can return many rows; therefore both statement count and rows/materialized metadata matter. A previously admitted scope cannot preserve revoked access. Fresh authority checks remain necessary before model and output boundaries.

### RAG query work

The native PostgreSQL lexical path uses full-text ranking. Its cost depends on postings visited and the `M` matches ranked; a bounded top-N sort can cost `O(M log p)`. The method name does not imply the Okapi BM25 formula.

Exact dense retrieval performs distance arithmetic proportional to `C × D`. An HNSW search instead performs distance work related to `V × D`, plus graph and heap operations. `V` is data-, filter- and configuration-dependent. Do not promise `O(log N)` latency from the presence of an index. PostgreSQL can choose another plan, and ANN filtering can require further traversal. Check the [pgvector indexing behavior](https://github.com/pgvector/pgvector#indexing) and the actual plan.

Fusion accumulates scores in `O(Qp)` work and sorts the union in `O(U log U)`, where `U ≤ 2Qp` for the document lexical/dense paths. Metadata filtering, hydration, provenance, curated knowledge and generation are additional stages. The [detailed scaling guide](knowledge-scaling.md) explains the candidate window and current scope guards.

### RLM query work

Metadata preparation is eager; document content is lazy. An action that reads one passage has a different cost from an action that scans all admitted text. For a trajectory with actions `j`, content processing depends on the sum of bytes actually inspected, `Σ B_j`, plus the work performed by those actions. Sorting extracted values or running repeated scans can add non-linear work. Iteration limits alone do not bound bytes processed per iteration.

Per-document page caching can avoid repeated object retrieval, while text joining or execution-level scans may still process the content again. Multiple self-consistency trajectories can multiply work. Provider tokens, CPU seconds in the application and CPU/GPU work inside a hosted model are different quantities. The last of these was not measured here and cannot be inferred from token totals alone.

### Structured questions

SQL over a dataset is a separate execution stage. A scan, indexed lookup, join and aggregation have different costs. RAG or RLM around that query does not remove the database's work. Record the source dataset revision, rows read and returned, plan, execution time, memory and spill information available from the engine. Preserve SQL and source provenance in the answer audit. This study does not yet provide a scale benchmark for the structured query engine.

## Measured metadata construction

The probe uses the actual `SourceRepository` and `CanonCorpusBuilder`, with an in-memory SQLite database. Every sample runs in a fresh subprocess. Fixture creation is excluded from elapsed and process CPU times; lifetime peak RSS includes imports and fixture creation. SQLite has just received the fixture, so these are not cold-disk observations. Other host workloads and OS caches were not controlled.

The host was macOS on ARM64 with 18 logical CPUs, Python 3.13.13 and SQLite 3.53.1. Each fixture stores twice the selected row count, plus three excluded rows. All selected sources deliberately share a filename to exercise collision handling. Every sample verifies complete membership, scope exclusion, the expected SQL count and no object reads.

Five samples per size produced these medians; ranges show the observed minimum and maximum, not confidence intervals or p95.

| Selected sources | Elapsed median (range) | Process CPU median | SQL statements |
| --- | --- | --- | --- |
| 100 | 5.8 ms (5.3–7.7 ms) | 5.2 ms | 1 |
| 1,000 | 30.6 ms (29.7–53.8 ms) | 27.9 ms | 5 |
| 10,000 | 503.8 ms (484.3–682.2 ms) | 458.8 ms | 50 |

Median **whole-process lifetime peak RSS** was approximately 161.1, 164.0 and 199.6 MiB respectively. This is not an allocation measurement for corpus construction and does not represent a complete API or worker process. In particular, no document bytes or immutable recorded views were loaded.

Keeping the selection at 100 sources while increasing the stored catalog to 50,003 rows gave a median of **15.4 ms elapsed** and **14.6 ms process CPU**, still with one SQL statement. The first-batch plans in both fixtures selected `ix_canon_sources_status`, rather than the source primary-key index. These fresh fixtures had no collected planner statistics. Statement count alone therefore does not establish independence from stored-corpus size. This observation is specific to the recorded SQLite plan; it is not a measured PostgreSQL regression.

A separate five-sample run collected SQLite statistics with `ANALYZE` before timing. The first-batch plan changed to the tenant/workspace index for 100 selected sources, and to the source primary-key index for 1,000 and 10,000 sources. The measured medians were:

| Selected sources | Elapsed median (range) | Process CPU median |
| --- | --- | --- |
| 100 | 26.0 ms (12.1–82.8 ms) | 7.0 ms |
| 1,000 | 132.9 ms (68.8–446.5 ms) | 38.4 ms |
| 10,000 | 683.3 ms (460.1–3,108.5 ms) | 338.8 ms |

The SQL counts stayed at 1, 5 and 50. Updated statistics changed the access plan; they did not produce a consistent wall-time improvement in this shared-host run. The large elapsed-time variation is why process CPU, planner evidence and host conditions must accompany a latency table. Compare representative plans and concurrent load on the target database before choosing an index or a capacity setting.

The operation counts agree with 200-ID batching. Three input sizes and five samples do not prove an asymptotic time bound; that analysis comes from the implementation. Host scheduling contributes to the difference between elapsed and process CPU time. These results establish neither a production worker size nor support for 10,000-source product answers across all existing evidence guards.

### Reproduce the metadata study

Use a clean checkout of the source revision to measure and a development environment with the locked native dependencies. Run from the repository root:

```bash
uv sync --project packages/canon --locked --extra dev

PYTHONPATH=packages/canon/src:packages/structured/src \
  packages/canon/.venv/bin/python tools/performance/corpus_metadata.py \
  --sizes 100 1000 10000 \
  --repeats 5 \
  --output /tmp/koinon-metadata-study/run.json
```

The command creates a JSON summary and one receipt per isolated sample. It refuses to overwrite an existing output. It contacts no model or external database and deletes no retained files. The receipt records source hashes, tool hash, runtime versions, sample sizes, wall time, process CPU, lifetime RSS and correctness checks.

To separate selected-scope growth from stored-catalog growth, repeat with `--sizes 100 --stored 50000` and a new output path. Add `--analyze` to collect SQLite statistics before the timed phase. Query-plan collection occurs outside timing and does not run a second measured construction. Review [the probe's scope and validation commands](https://github.com/fireflyframework/firefly-koinon/tree/main/tools/performance) before interpreting its results.

## Measured permission queries

The batching change was tested separately with session and scoped-token callers. For 201 documents, the SQLite baseline made **1,413** admission statements for a session and **2,823** for an asset-scoped token. The batched implementation made **8** and **9**, respectively. For 1,001 documents, those counts were **16** and **17**.

A real PostgreSQL run with 201 documents made **7** admission statements for a session and **8** for a scoped token. A fresh model-boundary check made **3** and **4**, respectively. Database-specific snapshot setup explains why these totals need not match SQLite. Tests verify separate serializable snapshots and access changes, including revoked membership, token access and ancestor permissions.

These are primary permission statements. They do not include the native retrieval, version, extraction, citation or model work measured in the next section. The original per-document growth was a real defect; the remaining bounded statement count is not a whole-request count.

## Measured native answers with real models

The retained fixture has two Markdown originals totaling 232 bytes, two chunks, 1,536-dimensional embeddings, an active embedding set, an HNSW index and a lexical GIN index. Models are Azure-hosted `gpt-4o-mini` and `text-embedding-3-small`. Each request runs sequentially against the same recorded source versions.

The factual question asks for an access-review interval and owner. The arithmetic question asks for the sum and difference of two recorded intervals. All source references and exact citation hashes were checked against immutable originals and extracted parts.

| Question and mode | Released baseline wall time | Retrieval-reuse source wall time | Source SQL statements |
| --- | --- | --- | --- |
| Factual, RAG | 3.427 s | 3.291 s | 107 |
| Arithmetic, RAG | 2.108 s | 2.184 s | 107 |
| Factual, RLM | 2.676 s | 3.662 s | 130 |
| Arithmetic, RLM | 4.247 s | 5.635 s | 130 |

These are individual observations, not a latency distribution. They do **not** show a consistent latency improvement. Provider-request wall time accounts for 2.864 s and 1.945 s of the two source RAG observations, and 3.092 s and 5.153 s of the RLM observations. The remaining time is not a CPU measurement; it also includes database, storage, scheduling and application work.

### What changed in RAG

The released path retrieved candidates once for search and again for answer generation. Exact-operation reuse reduces each measured RAG question from two embedding calls to one, two lexical queries to one and two dense queries to one. SQL statements decrease from **118 to 107**: nine scope/ANN-setting statements and the duplicate lexical and vector queries disappear.

Only ranked candidate identities and scores are reused. Current hydration, provenance and authority checks remain. Reuse does not cross operations, and query-expansion or reranking paths do not use this optimization. In these natural-language questions the lexical branch executes successfully but returns no matches; dense retrieval returns both documents. Separate exact-term lexical probes return the expected document.

### Tokens and output validity

| Source observation | Chat input / output tokens | Query embedding tokens | Chat calls |
| --- | --- | --- | --- |
| Factual, RAG | 442 / 69 | 15 | 1 |
| Arithmetic, RAG | 455 / 110 | 28 | 1 |
| Factual, RLM | 3,623 / 113 | 0 | 3 |
| Arithmetic, RLM | 5,151 / 217 | 0 | 4 |

Input totals include cached input where the provider reports it; cached tokens must not be added a second time. Initial ingestion separately used 40 embedding tokens in two requests. RLM's zero query embeddings do not erase that already-prepared fixture's ingestion cost.

The model produced the correct factual values and arithmetic in this small fixture. However, the native release contract returns exact source excerpts, and the separate final product renderer rejected unverified arithmetic value lineage. Therefore this is **native retrieval and evidence qualification**, not acceptance of a complete calculated chat answer. Better latency must never be obtained by bypassing that validation.

CPU, RSS and network transfer were not instrumented for these native answer runs. They remain unmeasured, not zero. The fixture also does not exercise authenticated persisted chat, SSE rendering, user concurrency, a large corpus or tenant isolation under load.

## Turn measurements into a cost estimate

Use the deployment's actual pricing, currency, region, model version and billing date. Keep cost estimates separate from an invoice. Hosted-model tokens do not expose the provider's internal CPU or GPU consumption.

For token-priced services, calculate each request from separately billed categories:

```text
model_cost = uncached_input_tokens × input_rate
           + cached_input_tokens × cached_input_rate
           + output_tokens × output_rate
           + embedding_tokens × embedding_rate
```

Rates in this equation are per token; divide a quoted price per million tokens by one million first. Add other modalities and cached-write categories only where the service bills them. Provisioned capacity needs its own time-based calculation. Failed requests, retries and cancelled work can still incur cost and must remain in usage accounting.

An installation's total also includes API and worker resource time, database baseline and growth, object storage, storage operations, network transfer and telemetry. Report a fixed baseline separately from incremental activity. If measuring a batch of uploads, allocate shared preparation cost explicitly rather than charging it again to each question.

Azure deployments can cross-check application receipts with [provider usage and latency metrics](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/monitor-openai). Other providers require the equivalent reconciliation. No currency total is published for the observations above because effective billed rates and billing reconciliation were not collected.

## Qualify the complete installation

Use an isolated deployment and representative, authorized data. A load generator should record intended arrival times as well as actual starts; otherwise a saturated client can hide server queueing. Increase the offered load gradually and stop on authority, evidence-integrity or resource failures.

| Dimension | Cases to include | Record and compare |
| --- | --- | --- |
| Corpus growth | 1,000, 10,000 and larger organization-representative source sets; fixed selection inside a growing catalog | Complete admitted coverage, rows examined, metadata RSS, authority and evidence costs |
| File growth | Supported small and large DOCX, XLSX, PPTX and PDF; dense cells, embedded images, OCR and archive expansion | Upload success, parser CPU/RSS, scratch and blob use, queue age, retries and searchable completion |
| Retrieval quality | Selective scopes, rare terms, mixed languages, known relevant passages and curated knowledge | Recall against an exact scoped baseline, valid citations, abstention and final answer correctness |
| Concurrency | 1, 5, 10, 25 and 50 active clients, with both short and long requests | Throughput, p50/p95/p99 from enough samples, errors, queue delay, pool wait, provider throttles and SSE first-content latency |
| Technique changes | RAG, RLM, changed embedding profile, missing views, cancellation and restart | Required work only, preparation duration, unchanged active mode on failure and revision-fenced activation |
| Security changes | Revoked project access, disabled tokens, changed source versions and concurrent deletion | No stale release or widened scope; explicit recoverable outcome |

Record a distinct result for admission, queue wait, object transfer, parsing, index work, provider requests, SQL execution, evidence verification, persistence and frontend rendering. A first SSE event is not necessarily first useful content. State exactly which event is timed.

For database investigations, capture sanitized `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` only in the controlled environment; it executes the query. Preserve row counts, loops, buffers, index choice and sort/spill behavior. PostgreSQL explains estimated versus actual work in its [EXPLAIN guide](https://www.postgresql.org/docs/current/using-explain.html).

The large-file, full-chat and sustained-concurrency rows above remain qualification work, not results established by the small native fixture. Use the current [scope and resource guards](knowledge-scaling.md#safety-limits-are-not-corpus-capacity-promises), [worker configuration](../operations/workers.md) and [index activation procedure](../operations/knowledge-indexes.md) when defining that environment. Do not raise constants or remove provenance checks to make a benchmark appear complete.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
