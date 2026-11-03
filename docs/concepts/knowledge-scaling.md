<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Knowledge scaling and query cost

koinon resolves the caller's authorized knowledge scope when a question is admitted. The corpus is not a fixed installation-time selection. Growth in stored files, authorized sources, chunks and document size affects different stages. A result limit or bounded model loop does not make all earlier work constant-time.

New questions can include newly available knowledge under the caller's current permissions. An already admitted operation keeps its selected source scope and rechecks access; it does not silently expand to documents added during execution. Revoked access cannot be preserved by an older scope or cached evidence.

This guide describes the native PostgreSQL document retrieval and recorded-view RLM paths. Other retrieval backends require their own query-plan and recall measurements. These are implementation cost bounds and a measurement procedure, not published throughput, cloud sizing or enterprise-capacity results.

## Name the input before describing complexity

| Variable | Meaning |
| --- | --- |
| `N` | Vector rows in the active embedding set, before the question's source restriction. |
| `C` | Chunks eligible under the query's SQL scope predicates. Physical rows or index nodes visited can exceed `C`. |
| `M` | Lexical matches that need ranking for one query variant. |
| `D` | Embedding dimensions. |
| `Q`, `p`, `k` | Actual query variants, per-modality candidate limit and final retrieval limit. |
| `U` | Distinct fused document candidates, at most `2 × Q × p` before the final window. |
| `A`, `F` | Selected source count and total size of filter inputs. |
| `S` | Workspace source count considered by the standalone unfiltered metadata path. |
| `B` | Original, normalized and text bytes actually read or processed; report these separately in measurements. |
| `I`, `R` | Effective RLM iteration allowance and self-consistency candidate count. |

The catalog authorization pass also has cost. A broad product search enumerates the current document catalog and checks candidate scope before passing admitted native IDs downstream. Improving native selected-source lookup does not remove that earlier catalog work.

## RAG: bounded candidates, query-plan-dependent retrieval

### Lexical search

The native method named `bm25_search` uses PostgreSQL `plainto_tsquery`, `ts_rank_cd`, rank ordering and a result limit. It is PostgreSQL full-text ranking, not a claim that the implementation computes the Okapi BM25 formula. Tenant, workspace and selected source predicates are in the SQL query. A GIN index exists for the text-search vector.

The query may process postings and rank `M` matches even when returning only `p` hits. A bounded top-N sort can require `O(M log p)` comparisons; a full sort can require `O(M log M)`. The plan, selectivity and available indexes determine the actual work. PostgreSQL explains the role and recheck behavior of [text-search indexes](https://www.postgresql.org/docs/current/textsearch-indexes.html).

### Dense vector search

The native pgvector path binds the active embedding set, validates dimensions, applies namespace/source predicates and orders by cosine distance. It supports a matching per-set HNSW index and requests `hnsw.ef_search` from configuration, with a default of `200`, plus relaxed iterative scanning. Physical index qualification checks readiness, validity, operator class, expression and set predicate; index activation also checks completed coverage.

An exact scan computes distances for eligible vectors, with distance arithmetic proportional to `C × D`, plus filtering and top-k selection. An HNSW plan visits some number `V` of candidates, giving distance work proportional to `V × D` plus graph and heap operations. `V` depends on data distribution, filters and search settings. There is no guaranteed `O(log N)` bound or automatic row-count threshold that makes every large query approximate. The `2,000`-dimension vector/halfvec boundary concerns representation, not corpus size.

pgvector distinguishes exact search from approximate indexes. With an approximate index, filtering can eliminate candidates after traversal; iterative scans may visit more candidates to find enough matches. SQL predicates still constrain returned rows. They do not prove that traversal touches only authorized candidates or that recall is complete. See the primary [pgvector indexing and filtering documentation](https://github.com/pgvector/pgvector#indexing).

A valid HNSW index is not proof that PostgreSQL selected it for a particular query. Inspect the actual plan. A missing active embedding set disables the dense half of native retrieval; lexical results must not be reported as successful dense retrieval.

### Fusion and later filters

For each of `Q` variants, native hybrid retrieval performs lexical retrieval, query embedding and dense retrieval. Reciprocal rank fusion accumulates candidate scores in `O(Qp)` work and sorts the union in `O(U log U)`. The document path retains a window of up to `3k` before batch metadata hydration and later filtering.

Source restrictions are passed into retrieval SQL. Domain, jurisdiction, tag, status and knowledge-item metadata checks occur after the candidate window is hydrated. This distinction matters: a selective later filter can return fewer than `k` hits even when matching content exists deeper in the corpus. The optional reranker processes a bounded candidate window; it does not scan all stored chunks. Curated retrieval has its separate governed path and merge, so the document-only candidate formula is not a complete cost model for mixed curated requests.

Organization settings bound retrieval `k` at `200`, per-query `p` at `500`, and expansion count at `10`. The public product search API separately accepts a result limit from `1` to `100`. These limits constrain different layers; none caps database rows examined, total stored knowledge or provider latency.

## RLM: lazy content, eager metadata and version pins

The product supplies dynamically admitted source IDs to the native corpus builder. That selected path deduplicates IDs and reads metadata in batches of at most `200`, enforcing tenant, workspace and status in the repository query. It does not enumerate unrelated workspace sources, issue a count for every page or stop after the first batch. Unknown or foreign IDs do not become an unrestricted fallback. An empty product-authorized scope produces no corpus; native standalone empty-filter semantics must not be used to widen it.

This describes the application rows requested and returned. PostgreSQL still chooses its physical access plan, so verify indexed lookups with representative `EXPLAIN` observations rather than inferring the plan from the batch size.

Filter membership sets are prepared once. With ordinary hash-table behavior, this costs `O(F)` preparation plus source and tag inspection. Selected rows are globally sorted by creation time and ID, costing `O(A log A)`, and retained in memory. Same-basename key allocation uses a per-base suffix cursor with amortized linear probes for repeated names, while checking the global used-key set to preserve literal-name collisions.

Every admitted recorded document is pinned to its exact version and extraction before analysis. This requires `O(A)` pin operations and metadata storage even when the model later reads only one document. Provenance and metadata preparation also visit the selected sources. The initial model discovery envelope lists at most `32` entries within `16,384` bytes and marks partial listings; that envelope is **not** a 32-document corpus limit.

Content is loaded lazily when a document helper actually reads it. The recorded-view reader verifies original and normalized artifacts, hashes recorded parts and constructs pages. Its work grows with the bytes and parts touched, rather than just the number of model iterations. Page caching avoids repeated object retrieval within the store; repeated string joins or action-level scans still process text. Highly fragmented same-page assembly can also incur repeated string-copy work.

The standalone native path without explicit source IDs still enumerates workspace metadata in `200`-row pages with OFFSET and repeated counts. It retains `O(S)` metadata; cumulative offset/count work can approach quadratic row-processing growth across pages. The product's admitted-ID path avoids this native enumeration, but does not make the whole engine linear or eliminate the earlier product authorization pass.

An RLM action can inspect one passage or scan all accessible text. Describe its cost using the bytes actually scanned per action across `I` iterations, nested calls and `R` candidates. Non-streaming self-consistency can run several candidates concurrently; streaming uses one trajectory. Token counts alone cannot establish model CPU operations, device memory or wall time: those also depend on model architecture, provider implementation, batching and hardware.

## Safety limits are not corpus-capacity promises

| Control | Current behavior | Interpretation |
| --- | --- | --- |
| Product search workspace groups | Default maximum `32` per call; exceeding it returns `SEARCH_SCOPE_TOO_WIDE`. | A single-call safety bound. The request is rejected, not silently truncated. It is not a limit on the caller's total authorized knowledge. |
| Explicit asset selection | At most `128` IDs in the product search request. | A request-shape limit; broader authorized scope can be resolved from a workspace or project. |
| Selected native metadata reads | Batches of `200`, with all admitted IDs considered. | Batch size, not a total source cap. |
| Recorded whole-document reader | Default normalized/text limit `64 MiB`, original limit `128 MiB`, at most `100,000` parts per document. | Per-document guards, not a total corpus memory budget. These are separate from upload capability limits. |
| RLM iterations and subcalls | Configured iterations `1–64`, subcall budget `0–128`, depth `0–8`, self-consistency `1–8`. Extended reasoning can double the effective iteration allowance. | Bounded actions do not imply bounded document bytes per action or constant model cost. |
| Secure execution | `64 MiB` VM memory; cooperative `300`-second lifetime per candidate and descendants; configured compute/request timeout defaults to `30` seconds. | Host metadata, readers and trusted I/O have their own work and deadlines. VM limits do not cap all process memory or forcibly interrupt a running host callback. |

A scheduler that transparently federates arbitrary authorized workspace counts, preserves complete coverage and combines verified evidence is not implemented. Narrow the question's scope after a broad-scope rejection. Do not invent a fixed installation corpus, silently select the first workspaces or claim complete coverage from partial execution.

## Measure the deployed path

Use a controlled environment and an authorized test corpus. This procedure proposes measurements; it does not report measured production performance.

1. Record the source revision, database and extension versions, active embedding set, dimensions, exact indexes, effective policy, model identity and machine resources. Separate cold-cache and warm-cache runs.
2. Vary `N`, `C`, `A`, document bytes, selectivity and workspace count independently. Keep the question and relevance expectations fixed when comparing retrieval plans. Include a small selected scope inside a much larger stored corpus.
3. Capture the exact lexical and vector SQL with representative bound values. Start with `EXPLAIN`; run `EXPLAIN (ANALYZE, BUFFERS)` only on the controlled read workload, because it actually executes the query. Record scan type, actual rows, loops, filtered rows, sort method, buffers and time. PostgreSQL's [EXPLAIN guide](https://www.postgresql.org/docs/current/using-explain.html) explains estimates versus execution observations.
4. Compare approximate retrieval with an exact baseline on the same authorized corpus and query vectors. Record recall as well as latency; a faster incomplete answer is not equivalent work.
5. Measure authorization/catalog enumeration, native metadata lookup, version pinning, bytes fetched, part verification, model requests and answer validation separately. Count database calls and peak host memory alongside elapsed time. Avoid recording source bodies or credentials in logs.
6. Exercise concurrent users, cancellation, revocation and scope-width rejection without changing live services. Record failures and incomplete coverage explicitly. Separate deterministic local tests from actual provider acceptance and sustained deployment throughput.

The repository's `packages/canon/tests/unit/rlm/test_corpus_scaling.py` checks bounded selected-ID batches, prepared filter sets, no unrelated metadata enumeration, lazy content and duplicate-name probe growth. These operation-count regressions are reproducible checks, not database benchmarks or enterprise sizing evidence. Backend `backend/tests/assistants/test_knowledge_policy.py` separately checks captured policy behavior across queued runs and retries; it does not exercise a real model.

## Implementation references

The following repository sources define the paths described here:

- [Product scope admission and workspace bound](https://github.com/fireflyframework/firefly-koinon/blob/main/backend/src/koinon/knowledge/service.py).
- [Retrieval orchestration and post-filter window](https://github.com/fireflyframework/firefly-koinon/blob/main/packages/canon/src/flycanon/core/services/retrieval/retrieval_service.py), [PostgreSQL lexical search](https://github.com/fireflyframework/firefly-koinon/blob/main/packages/canon/src/flycanon/core/services/retrieval/postgres_corpus.py) and [pgvector search](https://github.com/fireflyframework/firefly-koinon/blob/main/packages/canon/src/flycanon/core/services/retrieval/pgvector_store.py).
- [RLM corpus construction](https://github.com/fireflyframework/firefly-koinon/blob/main/packages/canon/src/flycanon/core/services/query/rlm/corpus.py) and [recorded whole-document reader](https://github.com/fireflyframework/firefly-koinon/blob/main/packages/canon/src/flycanon/core/services/sources/lineage/whole_read.py).

For changing behavior safely, use [Switch document answers between RAG and RLM](../operations/rag-rlm-switching.md). For index readiness, use [Build and activate a knowledge index](../operations/knowledge-indexes.md).

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
