<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Bounded Library file ingestion

koinon accepts queued Library originals up to **128 MiB per file**, in batches up to **512 MiB**. The direct synchronous upload endpoint remains limited to **32 MiB**. Use the source batch capabilities endpoint to discover the admitted queued limit, create a manifest, upload each original through the raw content endpoint, submit the batch, and poll its item/job status. A successful upload receipt means that the original was staged and verified; only a succeeded item with an immutable native receipt means that ingestion committed.

Chat attachment limits are separate. A Library limit does not raise the chat, image, MCP request-body or synchronous upload limit. External application review follows its separately advertised effective capability and approval flow.

## Installation policy

The actual installation profile is `koinon.knowledge.ingestion`. koinon binds this typed policy before native document and structured settings. A lower explicit bulk admission limit can further restrict the profile; a higher limit is rejected.

```yaml
koinon:
  knowledge:
    ingestion:
      raw_max_bytes: 134217728
      batch_max_bytes: 536870912
      lifetime_admission_bytes: 17179869184
      expanded_max_bytes: 268435456
      scratch_max_bytes: 1073741824
      child_rss_max_bytes: 805306368
      wall_seconds: 120
      text_max_bytes: 16777216
      chunks_max: 4096
    bulk:
      max_local_storage_operations: 1
  operations:
    admission:
      worker_capacity: 1
      api_capacity: 1
```

The mounted native JSON/base64 and URL compatibility intake paths retain a separate 32 MiB inline bound, including their legacy in-band bulk and replacement handlers. Their decoded-byte limit does not inherit the queued 128 MiB limit. Standalone native settings retain their existing explicitly configured behavior.

The native environment form is `PYFLY_KOINON_KNOWLEDGE_INGESTION_RAW_MAX_BYTES=134217728`, with the same prefix and uppercase field name for the other fields. These are byte counts and whole seconds, not human-readable size strings. Boolean, floating-point, negative and above-profile values are rejected. The synchronous setting remains `koinon.knowledge.max_upload_bytes` and must fit its 32 MiB path.

The **16 GiB lifetime admission budget** bounds retained staging attempts, including uncertain attempts. It is not a live-disk quota and is not credited automatically after processing, expiry or cancellation. This change neither deletes retained data nor introduces garbage collection. Plan an explicitly reviewed retention policy before exhausting this ledger; increasing the budget increases retained-byte exposure.

## Durable bytes and temporary scratch

Configure durable private Azure Blob or GCS object storage for staging and document originals. Local storage is a development option; container replicas must not use ephemeral local disk as their canonical original store. Queued file transport requires the pinned file methods of the storage adapter. The legacy synchronous S3 adapter does not currently implement this new queued file contract.

New document jobs persist a scoped object reference containing the route identity, exact provider version, SHA-256 and byte length. Their SQL payloads contain no original base64. A changed endpoint, container, prefix, provider version, size or hash fails closed. API and worker identities can differ; they must both have the exact reviewed storage permissions needed for their roles. The current authorization snapshot and worker lease remain mandatory independently of the storage receipt.

When staging and canonical document storage are different routes, the worker streams the verified original through owned scratch into a create-only canonical object. It does not reinterpret a reference as belonging to another bucket. Retries of the same operation reuse its verified original. Old retained base64 jobs remain readable with strict base64 validation and their original 32 MiB ceiling. There is no automatic rewrite, replay or cleanup of those jobs.

Uploads spool to an owned temporary file rather than accumulating a whole-file byte array. SDK file transfers use bounded chunks and exact version conditions. Cancellation drains admitted SDK operations before releasing the caller's scratch file. Document parsing runs in an owned subprocess; its process group is terminated and waited for on cancellation, deadline or resource failure. The scratch budget includes the original spool and bounded parser output. API bulk bodies, external-review preparation and original downloads share one fail-fast per-process scratch admission component. Each reserves twice its admitted original size before file I/O. Capability and stage admission honor a smaller configured scratch budget; no hidden minimum silently increases it. Provision sufficient ephemeral container storage and account for every enabled concurrent operation.

## Office extraction and honest coverage

DOCX and PPTX use streamed OOXML parsing after an actual-byte expansion and XML preflight. Duplicate/encrypted entries, unsafe package paths, DTD/entity declarations in UTF-8 or UTF-16, excessive expansion and excessive text are rejected. The parser follows package relationships and declared main parts. Presentation slide order and slide numbers are preserved; document paragraphs, table text, headers and footers are retained with distinct section provenance. Physical DOCX page numbers are unavailable without a layout engine and are not invented.

Coverage is **text and tables**. Original image/media bytes remain in the durable original; this path does not interpret their visual content. A small extracted text result from an image-heavy file is not complete multimodal understanding. Metadata records this boundary. Optional PDF OCR remains separately configured and depends on installed tools or optional model packages. The base profile does not imply that OCR, a vision provider or local models are installed.

A file below 128 MiB can still exceed expanded, text, section/chunk, scratch, memory or time limits. Such a file fails explicitly; content is never silently truncated. A 2 GiB worker is a candidate deployment profile, not proof that arbitrary 128 MiB files fit. Qualify actual formats, native persistence, provider transfers and the final Linux image under its real resource limits. Bound global work admission and reader/SDK concurrency rather than multiplying independent queue limits.

## Readback and migrations

Whole-document and exact-part reads retain their normalized text/part budgets while verifying pinned originals up to 128 MiB through bounded scratch. They preserve the immutable source/extraction chain and current authorization checks. The current-original and exact-version download endpoints stream a verified owned spool in 64 KiB frames up to 128 MiB. They recheck current policy and the pinned binding before releasing frames and the final response cut; token revocation or a changed current head interrupts subsequent release. They hold one per-process download slot and twice the original size in the shared API scratch ledger until completion, failure or disconnect, with a 120-second response deadline. A read never returns a private object path or signed cloud URL. This does not raise a model-context limit.

Apply the additive primary migration `koinon_0032_large_files` and document migration `0021_pinned_originals` before starting the new runtime. Published migrations are unchanged. Existing rows keep their original identities and quotas. Downgrades refuse to discard new pinned receipts or admissions that exceed the previous schema bounds; review application rollback compatibility before accepting larger files.
