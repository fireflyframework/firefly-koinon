<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Choose an intake mode and file format

Choose the destination by what you want to do with the content. Use a **document** to read and search passages, a **dataset** to explore tables and calculate results, or a **private chat attachment** to supply context to one conversation. A filename alone does not choose the mode or grant access.

## Pick the right path

| Destination | Suitable files and behavior | What to check |
| --- | --- | --- |
| Documents uploaded to the Library for reading and search | Text and Markdown; HTML, XML and JSON; PDF, DOCX, XLSX, PPTX and RTF; OpenDocument text, spreadsheets and presentations; CSV/TSV; supported transcript and image extraction | The operator's installed normalizers, loaders and OCR prerequisites. Check processing completion, original source and extracted passages. |
| Data uploaded to the Library for queries | CSV/TSV, XLSX/XLS/ODS, JSON/JSONL/NDJSON, Parquet, Avro, ORC and Arrow/Feather | A file can yield several tables. Inspect sheet/section boundaries, column names and inferred types before querying. Required reader dependencies must be installed. |
| Files attached to a chat | Text/Markdown, CSV/TSV, JSON, HTML, XML, PDF, DOCX, XLSX, PPTX, still PNG/JPEG/WebP/GIF images and ZIP bundles advertised by the conversation's capabilities | Private storage, current ownership/access, extraction worker and per-format dependencies. Select the specific ready attachment IDs to use in a message. |

These are implemented format families, not a claim that every deployment has every converter or model capability enabled. An encrypted or corrupt file, a content/extension mismatch or a missing parser can still fail processing. Review the reported reason before retrying. Do not rename an unsupported binary file to a supported extension.

For a spreadsheet, choose **Data to explore with queries** when you need row filters, aggregation or SQL. Choose **Documents to read and search** when you need its extracted text. These paths create different knowledge resources; choosing one does not automatically create the other. The structured spreadsheet reader can identify multiple sections in a sheet instead of treating every workbook as one CSV-like table.

Structured compression supports gzip, bzip2 and ZIP around a detected data file. A structured ZIP must contain exactly one data file; it is not a multi-file batch. Expansion limits, parsing resources and object-storage limits remain separate from the compressed upload size.

## Check extraction and multimodal availability

Text extraction, OCR, image validation and model vision are separate capabilities:

- A digital PDF may provide text directly. A scanned PDF needs an available OCR path; a PDF upload alone does not establish that its pages were read correctly.
- Image intake can require OCR tools and language data. Private chat accepts still images; animation is rejected. A verified image does not establish that the selected model supports vision.
- Document normalization can convert additional image types, archives, email or media into supported artifacts when the operator has installed and configured the required adapters. Existing transcript loaders do not, by themselves, supply audio transcription.
- Docling is an optional layout-aware PDF OCR path. Its dependencies and runtime resources must be configured by the operator. Enabling it does not remove file, extraction or model-context limits.

The API exposes deployment observations at `GET /api/v1/capabilities`. For private chat, use `GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/capabilities` for that authorized conversation. Its typed response reports format extensions, extraction prerequisites and the effective limits. A null availability observation means unknown; configured storage or an installed parser is not a completed processing job. Library intake still requires validation of a representative file in the selected mode; the general capability response is not an exhaustive Library format registry.

## Understand the limits

The following are current defaults. Deployment configuration and the returned private-chat capabilities determine the effective values.

| Boundary | Default or explicit behavior |
| --- | --- |
| Library upload | One file per request; 32 MiB default file limit. Uploading in the interface can send several separate requests. |
| Append to an existing dataset | One multipart file and a stable `Idempotency-Key`; the same upload byte limit. At most 128 new parsed tables in that append operation. |
| Private chat file | 20 MiB per document/archive file; 8 MiB per image. |
| Private conversation allowance | 100 files and 128 MiB total; at most 10 selected attachments per message. |
| Private extraction | Up to 60 seconds per extraction; defaults include 32 MiB expanded content, 8 artifacts, 200 pages and 2 MiB normalized text. These are separate from the original upload size. |
| Private file retention | 24-hour default expiry. Expiry changes access to the original; a retained answer's recorded evidence does not recreate expired bytes. |
| Blob transport | Azure/GCS and the configured private object profile have their own bounded object limits, commonly 64 MiB. A storage limit is not permission to exceed an upload or extraction limit. |

Model context has its own bounds. A large accepted file is not necessarily inserted in full into every model request. Inspect the answer's source and execution audit to understand which available content was used.

## Confirm processing before asking questions

For Library content:

1. Choose the organization, workspace and destination folder you are authorized to maintain.
2. Review the mode and files, then upload. Follow the observed processing state rather than assuming accepted bytes are searchable.
3. Open the resulting document passages or dataset schema. Verify extraction and table boundaries against the original.
4. Ask a small question, then inspect the answer's audit and source references. [Versions and lineage](lineage.md) explains the original file, extraction, source parts and table snapshots.

For private chat, wait for the selected attachments to become ready. Failed or expired items need review; selecting a file does not make it ready. Private attachments remain bound to their owner and conversation. They do not enter the organization's Library automatically. Adding or replacing organizational knowledge is a separate reviewed operation with its own current permissions and revision checks.

## Multiple files and bulk loading

Multiple selection in the interface and a loop in an SDK send separate uploads. They do not provide an all-or-nothing batch or automatic recovery across files. Library upload is synchronous. Dataset append has durable idempotency and publication guards, but it is not asynchronous bulk intake: partial native effects can require reconciliation after failure. Do not retry an unfinished append with a fresh key to bypass its retained state.

A general durable bulk-loading/query-batch API is not currently provided. Use bounded sequential calls with per-file results, preserve returned identifiers and inspect failures before retrying. See the [Python](headless-python.md), [TypeScript](headless-typescript.md) and [Java](headless-java.md) SDK guides for the supported flow, and [file persistence and storage](../operations/storage.md) for the remaining bulk contract and cloud-operation boundaries.
