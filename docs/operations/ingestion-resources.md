<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Ingestion memory, concurrency and scratch

Private object storage keeps originals durable across replicas. Parsing uses private
ephemeral scratch for verified downloads, row spools, intermediate text, Parquet and
native spill files. Scratch is neither the authoritative original nor a shared
staging filesystem.

## Use the shared Library profile

The mounted product uses the typed `koinon.knowledge.ingestion` profile. Its default
bounds are 128 MiB per original, 256 MiB expanded content, 1 GiB tracked scratch,
768 MiB sampled parser-child RSS and a 120-second parser deadline. The
[Library ingestion reference](../reference/library-file-ingestion.md) documents
batch, lifetime-admission, document-text and chunk limits and their environment
names. These installation settings govern Library ingestion; chat attachments and
synchronous review APIs have separate limits.

Structured ingestion receives the exact raw-byte limit, expansion, scratch, child
RSS and deadline values through its native settings bean. Odd byte limits remain
exact; they are not rounded down to whole MiB. Standalone structured deployments
without the mounted Library profile retain their existing settings and aliases.

## Configure the native engines separately

The shared profile supplies the indicated native fields when mounted. The
remaining engine controls still need explicit deployment configuration. The table
describes their behavior and the values used during qualification; it does not
introduce additional canonical configuration aliases.

| Field | Standalone default | Mounted profile or small-worker candidate |
| --- | --- | --- |
| `max_file_bytes` | unset; legacy `max_file_mb` applies | Exact shared raw-byte bound |
| `ingest_duckdb_memory_limit` | `512MiB` | Set `128MiB` for the qualified candidate |
| `ingest_duckdb_threads` | `1` | Keep `1` |
| `ingest_native_connections` | `32` | Set `1` |
| `ingest_scratch_max_bytes` | `8589934592` | Shared profile: `1073741824` |
| `ingest_decompressed_max_bytes` | `5368709120` | Shared profile: `268435456` |
| `ingest_reader_rss_max_bytes` | `805306368` | Shared profile: `805306368` |
| `ingest_reader_timeout_seconds` | `120` | Shared profile: at most `120` |
| `ingest_excel_max_cells` | `2000000` | Used rectangle, including empty cells |
| `ingest_excel_max_rows` | `1000000` | Spreadsheet row-axis bound |
| `ingest_excel_max_columns` | `4096` | Spreadsheet column-axis bound |
| `ingest_shared_strings_max_bytes` | `33554432` | Expanded OOXML shared-string parts |
| `ingest_scratch_root` | unset | Existing canonical directory for private scratch |

A mounted installation uses one canonical profile, for example:

```yaml
koinon:
  knowledge:
    ingestion:
      raw_max_bytes: 134217728
      expanded_max_bytes: 268435456
      scratch_max_bytes: 1073741824
      child_rss_max_bytes: 805306368
      wall_seconds: 120
```

For generated artifacts, the supported storage profile also accepts:

```yaml
koinon:
  storage:
    structured:
      max_object_bytes: 268435456
```

The object-store bound accommodates generated artifacts; it does not raise the
Library original-upload limit. Query execution retains its separate
`duckdb_memory_limit` and admission policy. Use the process-wide heavy-work budget
in [worker roles](workers.md), including communication delivery, rather than
assuming one task per queue means one active task overall.

## Preserve complete tables and source coordinates

Before native XLSX allocation, ingestion streams archive members to check actual
expanded bytes, declared worksheet and shared-string parts, XML entity declarations
and the used cell rectangle. Worksheet XML may use the total expansion budget;
shared-string parts have their tighter bound. Sparse dimensions and custom OOXML
part names receive the same checks. Oversized inputs fail explicitly; rows are
never silently truncated to satisfy a budget.

Spreadsheet rows are iterated into an accounted disk spool. Section detection and
materialization retain sparse columns, inherited headers and absolute source-cell
coordinates without whole-sheet Python copies. CSV coordinate capture streams
physical lines and stores contiguous source positions as ranges. Coordinate and
rejection receipts have explicit bounds. Native Parquet writes use small row groups,
and publication uses bounded file transport. Legacy byte-only stores support only
an explicit small-artifact compatibility path of at most 1 MiB.

Resource exhaustion is an `INGEST_RESOURCE_LIMIT` failure. Sampling and statistics
cannot convert it into successful partial processing or retry with an unbounded
connection. Keep durable originals and receipts; do not reset attempts or replay
an operation with an unknown external outcome.

## Qualify the complete worker

A source-only measurement used a valid 134,214,314-byte XLSX workbook with 93,990
data rows and eight columns. With worker composition loaded, enumeration,
materialization and owned local file publication retained every row and complete
coordinates at approximately 700 MiB combined parent-and-child peak RSS. A
128,048,925-byte CSV retained 240,000 rows and six columns at approximately 271 MiB
in its isolated reader measurement. These synthetic local measurements establish
neither cloud throughput nor a started-worker or managed-container memory guarantee.

Include native children, model/client buffers, other consumers, old/new revision
overlap and representative formats when qualifying an actual 2 GiB worker. DuckDB's
memory setting covers its engine, not total RSS. Spreadsheet processes inherit the
owner's process group. Cancellation drains their termination; a kernel deadline
remains active if the monitor disappears, and Linux also arms parent-death
termination. RSS admission is sampled, so it is not a kernel-enforced memory ceiling.

The parent tracks originals, decompressed inputs and completed outputs. A spreadsheet
child reserves its share of that remaining budget; it does not receive another full
budget. Its private working tree includes the row spool, intermediate CSV, Parquet,
metadata and DuckDB spill. The original is counted once across the parent and child.
A live 20 ms monitor terminates observed over-budget work and drains it before
publication. Accounting also rejects an oversized result before it becomes a
successful artifact.

These are logical admission and sampled enforcement bounds. A native writer can
transiently overshoot between checks; a filesystem or container quota is required
for a physical disk ceiling. API staging and cloud verification need their own
bounded reservations and physical headroom. A provider may hold another copy of the
current artifact while verifying it; generated artifacts can be larger than their
originals. Do not interpret the 1 GiB parser budget as a 1 GiB limit on the entire
container volume, or infer total scratch from the 128 MiB original-upload limit.

Retained-read bounds must continue to cover previously admitted originals, even
when new-upload limits are lowered.
