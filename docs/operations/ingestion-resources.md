<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Ingestion memory, concurrency and scratch

Private object storage makes originals durable across replicas. Parsing still needs
memory and local scratch: the original byte buffer, decompressed input, spreadsheet
or JSON structures, intermediate CSV/JSONL, Parquet outputs and native spill files.
That scratch can be private ephemeral storage; it is not the authoritative original
or a shared staging filesystem.

## Configure ingestion separately from query execution

The following typed `FlyquerySettings` fields use the `FLYQUERY_` environment prefix:

| Field | Default | Effect |
| --- | --- | --- |
| `ingest_duckdb_memory_limit` | `512MiB` | Explicit memory setting on every ingestion DuckDB connection |
| `ingest_duckdb_threads` | `1` | Native threads per ingestion connection |
| `ingest_native_connections` | `32` | Process-wide upper bound on simultaneous ingestion native connections |
| `ingest_scratch_max_bytes` | `8589934592` | Aggregate tracked scratch budget per ingestion operation |
| `ingest_decompressed_max_bytes` | `5368709120` | Streaming decompression bound, also subject to the retained five-GiB safety cap |
| `ingest_scratch_root` | unset | Optional existing canonical parent for private per-connection spill directories |

Query execution retains its separate `duckdb_memory_limit` setting. Changing that
query limit does not configure ingestion readers. Conversely, an ingestion limit
does not bound query execution or document normalization.

All ingestion DuckDB connections use the selected memory/thread policy and bounded
private spill directories. Operation context follows native calls into their owned
threads. Receive, parse, sample and profile stages share the enclosing ingestion
budget; entering a nested stage cannot reset it. Exhausted memory, spill, scratch or
connection admission is an explicit `INGEST_RESOURCE_LIMIT` failure. Statistics or
sampling code cannot turn that failure into successful partial processing or retry
with an unbounded connection. Supported file formats and successful row contents
remain unchanged.

## Size a small candidate from measured work

For a light-work measurement, an operator could start with:

```sh
FLYQUERY_MAX_FILE_MB=4
FLYQUERY_INGEST_WORKER_CONCURRENCY=1
FLYQUERY_INGEST_SECTION_CONCURRENCY=1
FLYQUERY_INGEST_DUCKDB_MEMORY_LIMIT=256MiB
FLYQUERY_INGEST_DUCKDB_THREADS=1
FLYQUERY_INGEST_NATIVE_CONNECTIONS=1
FLYQUERY_INGEST_SCRATCH_MAX_BYTES=268435456
FLYQUERY_INGEST_DECOMPRESSED_MAX_BYTES=67108864
```

These are inputs to qualification, not a minimum-memory guarantee. Align direct
document limits, [bulk limits](durable-bulk.md), query memory and every other worker
consumer's concurrency. One task per queue kind can still produce several active
tasks in the same process. Include old/new revision overlap and native children.
Do not lower retained-read bounds below previously admitted originals without a
reviewed plan that preserves their retrieval.

DuckDB's memory setting is not a total-process RSS limit. Python, Calamine, Arrow,
document normalization, model/client buffers and OCR can allocate outside that
budget. Docling is optional and lazy, but its absence does not disable the PDF
loader's Tesseract fallback. This change does not route heavy work to a separate
pool. Qualify the actual installed artifact, representative input formats and
concurrent MCP/worker journeys before accepting a small container allocation.

## Scratch enforcement and physical limits

Source, decompression and text copies check their budgets before writing excess
bytes. Native spill is constrained with DuckDB's `max_temp_directory_size`. Native
Parquet/Arrow outputs are checked before they can become successful artifacts, and
the existing operation owner reclaims failed temporary outputs after native work
drains. See [DuckDB configuration](https://duckdb.org/docs/2.0/configuration/overview)
for its engine settings.

Native output writers can temporarily exceed the tracked-output limit before their
call returns. Use an actual filesystem/container scratch quota when a physical disk
ceiling is required. Cancellation cannot interrupt an arbitrary C++ call safely;
owned calls drain before their paths are reclaimed, and the platform still needs a
reviewed termination/deadline policy. Do not describe these application checks as a
hard RSS limit or a physical filesystem quota.

Keep durable originals and operation receipts when resource exhaustion occurs.
Reducing resource use must not silently truncate tables, drop originals, reset
attempt counters or replay an operation with an unknown native outcome.
