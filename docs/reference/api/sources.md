<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Sources, files and lineage

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Upload](#knowledgecontroller-upload) (POST)
- [Schema](#knowledgecontroller-schema) (GET)
- [Lineage](#knowledgecontroller-lineage) (GET)
- [Document chunks](#knowledgecontroller-document-chunks) (GET)
- [Document original](#knowledgecontroller-document-original) (GET)
- [Reingest document](#contentcontroller-reingest-document) (POST)
- [Reingest table](#contentcontroller-reingest-table) (POST)
- [Document](#contentcontroller-document) (POST)
- [Table](#contentcontroller-table) (POST)
- [Append](#datasetfilescontroller-append) (POST)
- [Versions](#documenthistorycontroller-versions) (GET)
- [Version](#documenthistorycontroller-version) (GET)
- [Extractions](#documenthistorycontroller-extractions) (GET)
- [Parts](#documenthistorycontroller-parts) (GET)
- [Part](#documenthistorycontroller-part) (GET)
- [Original](#documenthistorycontroller-original) (GET)
- [Snapshot](#tableprovenancecontroller-snapshot) (GET)
- [History](#tableprovenancecontroller-history) (GET)
- [Manifest](#tablecoordinatecontroller-manifest) (GET)
- [Cells](#tablecoordinatecontroller-cells) (POST)
- [Rows](#tablecoordinatecontroller-rows) (GET)
- [Columns](#tablecoordinatecontroller-columns) (GET)

<!-- operation: KnowledgeController.upload -->
<a id="knowledgecontroller-upload"></a>
## Upload

```http
POST /api/v1/tenants/{tenant_id}/sources/upload
```

Contract operation: `KnowledgeController.upload`.

| SDK | Method |
| --- | --- |
| Python | `upload` |
| TypeScript | `sources.uploadFile` |
| Java | `client.sources.upload` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceUpload`](../models/sourceupload.md) |
| Response schema | [`UploadResponse`](../models/uploadresponse.md) |
| Success status | `201` |
| Declared encoding | `multipart/form-data` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeController.schema -->
<a id="knowledgecontroller-schema"></a>
## Schema

```http
GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/schema
```

Contract operation: `KnowledgeController.schema`.

| SDK | Method |
| --- | --- |
| Python | `schema` |
| TypeScript | `dataset.schema` |
| Java | `client.datasets.schema` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DatasetSchema`](../models/datasetschema.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeController.lineage -->
<a id="knowledgecontroller-lineage"></a>
## Lineage

```http
GET /api/v1/tenants/{tenant_id}/lineage
```

Contract operation: `KnowledgeController.lineage`.

| SDK | Method |
| --- | --- |
| Python | `lineage` |
| TypeScript | `lineage` |
| Java | `client.knowledge.lineage` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `asset_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Lineage`](../models/lineage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeController.document_chunks -->
<a id="knowledgecontroller-document-chunks"></a>
## Document chunks

```http
GET /api/v1/tenants/{tenant_id}/documents/{document_id}/chunks
```

Contract operation: `KnowledgeController.document_chunks`.

| SDK | Method |
| --- | --- |
| Python | `document_chunks` |
| TypeScript | `documents.chunks` |
| Java | `client.documents.chunks` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `offset` | query | `QueryParam[int]` | No | `0` |
| `limit` | query | `QueryParam[int]` | No | `50` |
| `page` | query | <code>QueryParam&#91;int &#124; None&#93;</code> | No | `null` |
| `section` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `q` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DocumentChunks`](../models/documentchunks.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeController.document_original -->
<a id="knowledgecontroller-document-original"></a>
## Document original

```http
GET /api/v1/tenants/{tenant_id}/documents/{document_id}/original
```

Contract operation: `KnowledgeController.document_original`.

| SDK | Method |
| --- | --- |
| Python | `document_download` |
| TypeScript | `documents.download` |
| Java | `client.documents.original` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`BinaryDownload`](../models/binarydownload.md) |
| Success status | `200` |
| Declared encoding | `binary` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentController.reingest_document -->
<a id="contentcontroller-reingest-document"></a>
## Reingest document

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/reingest
```

Contract operation: `ContentController.reingest_document`.

| SDK | Method |
| --- | --- |
| Python | `reingest_document` |
| TypeScript | `documents.reingest` |
| Java | `client.documents.reingest` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[DocumentReingestInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`DocumentReingestInput`](../models/documentreingestinput.md) |
| Response schema | [`ContentUpdate`](../models/contentupdate.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `If-Match (unquoted digest/snapshot helper argument; quoted wire header)`
- `X-Koinon-Source-Version (optional UUID paired with extraction)`
- `X-Koinon-Extraction (optional ingestion UUID paired with source version)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentController.reingest_table -->
<a id="contentcontroller-reingest-table"></a>
## Reingest table

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/reingest
```

Contract operation: `ContentController.reingest_table`.

| SDK | Method |
| --- | --- |
| Python | `reingest_table` |
| TypeScript | `dataset.reingestTable` |
| Java | `client.datasets.reingestTable` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[TableReingestInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`TableReingestInput`](../models/tablereingestinput.md) |
| Response schema | [`ContentUpdate`](../models/contentupdate.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `If-Match (unquoted digest/snapshot helper argument; quoted wire header)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentController.document -->
<a id="contentcontroller-document"></a>
## Document

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/content
```

Contract operation: `ContentController.document`.

| SDK | Method |
| --- | --- |
| Python | `replace_document` |
| TypeScript | `documents.replace` |
| Java | `client.documents.replace` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`DocumentReplacement`](../models/documentreplacement.md) |
| Response schema | [`ContentUpdate`](../models/contentupdate.md) |
| Success status | `201` |
| Declared encoding | `multipart/form-data` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `If-Match (unquoted digest/snapshot helper argument; quoted wire header)`
- `X-Koinon-Source-Version (optional UUID paired with extraction)`
- `X-Koinon-Extraction (optional ingestion UUID paired with source version)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentController.table -->
<a id="contentcontroller-table"></a>
## Table

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/content
```

Contract operation: `ContentController.table`.

| SDK | Method |
| --- | --- |
| Python | `replace_table` |
| TypeScript | `dataset.replaceTable` |
| Java | `client.datasets.replaceTable` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`TableReplacement`](../models/tablereplacement.md) |
| Response schema | [`ContentUpdate`](../models/contentupdate.md) |
| Success status | `201` |
| Declared encoding | `multipart/form-data` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `If-Match (unquoted digest/snapshot helper argument; quoted wire header)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DatasetFilesController.append -->
<a id="datasetfilescontroller-append"></a>
## Append

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/files
```

Contract operation: `DatasetFilesController.append`.

| SDK | Method |
| --- | --- |
| Python | `append_dataset_file` |
| TypeScript | `dataset.appendFile` |
| Java | `client.datasets.appendFile` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`DatasetFileUpload`](../models/datasetfileupload.md) |
| Response schema | [`DatasetFileAppendResult`](../models/datasetfileappendresult.md) |
| Success status | `201` |
| Declared encoding | `multipart/form-data` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryController.versions -->
<a id="documenthistorycontroller-versions"></a>
## Versions

```http
GET /api/v1/tenants/{tenant_id}/documents/{document_id}/versions
```

Contract operation: `DocumentHistoryController.versions`.

| SDK | Method |
| --- | --- |
| Python | `document_versions` |
| TypeScript | `documents.versions` |
| Java | `client.documents.versions` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DocumentVersionPage`](../models/documentversionpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryController.version -->
<a id="documenthistorycontroller-version"></a>
## Version

```http
GET /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}
```

Contract operation: `DocumentHistoryController.version`.

| SDK | Method |
| --- | --- |
| Python | `document_version` |
| TypeScript | `documents.version` |
| Java | `client.documents.version` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DocumentVersion`](../models/documentversion.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryController.extractions -->
<a id="documenthistorycontroller-extractions"></a>
## Extractions

```http
GET /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}/extractions
```

Contract operation: `DocumentHistoryController.extractions`.

| SDK | Method |
| --- | --- |
| Python | `document_extractions` |
| TypeScript | `documents.extractions` |
| Java | `client.documents.extractions` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DocumentExtractionPage`](../models/documentextractionpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryController.parts -->
<a id="documenthistorycontroller-parts"></a>
## Parts

```http
GET /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}/extractions/{extraction_id}/parts
```

Contract operation: `DocumentHistoryController.parts`.

| SDK | Method |
| --- | --- |
| Python | `document_parts` |
| TypeScript | `documents.parts` |
| Java | `client.documents.parts` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |
| `extraction_id` | path | `PathVar[str]` | Yes | Not specified |
| `kind` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DocumentPartPage`](../models/documentpartpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryController.part -->
<a id="documenthistorycontroller-part"></a>
## Part

```http
GET /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}/extractions/{extraction_id}/parts/{source_part_id}
```

Contract operation: `DocumentHistoryController.part`.

| SDK | Method |
| --- | --- |
| Python | `document_part` |
| TypeScript | `documents.part` |
| Java | `client.documents.part` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |
| `extraction_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_part_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DocumentPartContent`](../models/documentpartcontent.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryController.original -->
<a id="documenthistorycontroller-original"></a>
## Original

```http
GET /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}/original
```

Contract operation: `DocumentHistoryController.original`.

| SDK | Method |
| --- | --- |
| Python | `document_version_original` |
| TypeScript | `documents.versionOriginal` |
| Java | `client.documents.versionOriginal` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`BinaryDownload`](../models/binarydownload.md) |
| Success status | `200` |
| Declared encoding | `binary` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableProvenanceController.snapshot -->
<a id="tableprovenancecontroller-snapshot"></a>
## Snapshot

```http
GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/provenance
```

Contract operation: `TableProvenanceController.snapshot`.

| SDK | Method |
| --- | --- |
| Python | `table_provenance` |
| TypeScript | `dataset.tableProvenance` |
| Java | `client.datasets.tableProvenance` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `snapshot_id` | query | `QueryParam[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`TableProvenance`](../models/tableprovenance.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableProvenanceController.history -->
<a id="tableprovenancecontroller-history"></a>
## History

```http
GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/snapshots
```

Contract operation: `TableProvenanceController.history`.

| SDK | Method |
| --- | --- |
| Python | `table_snapshots` |
| TypeScript | `dataset.tableSnapshots` |
| Java | `client.datasets.tableSnapshots` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`TableSnapshotPage`](../models/tablesnapshotpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableCoordinateController.manifest -->
<a id="tablecoordinatecontroller-manifest"></a>
## Manifest

```http
GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates
```

Contract operation: `TableCoordinateController.manifest`.

| SDK | Method |
| --- | --- |
| Python | `table_coordinates` |
| TypeScript | `dataset.tableCoordinates` |
| Java | `client.datasets.tableCoordinates` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `snapshot_id` | query | `QueryParam[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`TableCoordinateManifest`](../models/tablecoordinatemanifest.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableCoordinateController.cells -->
<a id="tablecoordinatecontroller-cells"></a>
## Cells

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates/cells
```

Contract operation: `TableCoordinateController.cells`.

| SDK | Method |
| --- | --- |
| Python | `table_coordinate_cells` |
| TypeScript | `dataset.tableCoordinateCells` |
| Java | `client.datasets.tableCoordinateCells` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[CoordinateCellRequest]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`CoordinateCellRequest`](../models/coordinatecellrequest.md) |
| Response schema | [`TableCoordinateSelection`](../models/tablecoordinateselection.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableCoordinateController.rows -->
<a id="tablecoordinatecontroller-rows"></a>
## Rows

```http
GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates/rows
```

Contract operation: `TableCoordinateController.rows`.

| SDK | Method |
| --- | --- |
| Python | `table_coordinate_rows` |
| TypeScript | `dataset.tableCoordinateRows` |
| Java | `client.datasets.tableCoordinateRows` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `snapshot_id` | query | `QueryParam[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`TableRowRangePage`](../models/tablerowrangepage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableCoordinateController.columns -->
<a id="tablecoordinatecontroller-columns"></a>
## Columns

```http
GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates/columns
```

Contract operation: `TableCoordinateController.columns`.

| SDK | Method |
| --- | --- |
| Python | `table_coordinate_columns` |
| TypeScript | `dataset.tableCoordinateColumns` |
| Java | `client.datasets.tableCoordinateColumns` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `snapshot_id` | query | `QueryParam[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`TableColumnBindingPage`](../models/tablecolumnbindingpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
