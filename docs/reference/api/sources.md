<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Sources, files and lineage

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Get](#sourcecapabilitiescontroller-get) (GET)
- [List](#contentconnectionscontroller-list) (GET)
- [Get](#contentconnectionscontroller-get) (GET)
- [Disconnect](#contentconnectionscontroller-disconnect) (POST)
- [Sites](#contentconnectionscontroller-sites) (GET)
- [Drives](#contentconnectionscontroller-drives) (GET)
- [Children](#contentconnectionscontroller-children) (GET)
- [Mappings page](#sourcemappingcontroller-mappings-page) (GET)
- [Get](#sourcemappingcontroller-get) (GET)
- [Runs](#sourcemappingcontroller-runs) (GET)
- [Initial operation](#sourcemappingcontroller-initial-operation) (GET)
- [Operation](#sourcemappingcontroller-operation) (GET)
- [Run](#sourcemappingcontroller-run) (GET)
- [Run items](#sourcemappingcontroller-run-items) (GET)
- [Cancel](#sourcemappingcontroller-cancel) (POST)
- [Retry](#sourcemappingcontroller-retry) (POST)
- [Review](#sourcemappingcontroller-review) (POST)
- [Items](#sourcemappingcontroller-items) (GET)
- [Create](#sourcemappingcontroller-create) (POST)
- [Revise](#sourcemappingcontroller-revise) (POST)
- [Apply](#sourcemappingcontroller-apply) (POST)
- [Sync](#sourcemappingcontroller-sync) (POST)
- [Pause](#sourcemappingcontroller-pause) (POST)
- [Resume](#sourcemappingcontroller-resume) (POST)
- [Retire](#sourcemappingcontroller-retire) (POST)
- [Begin](#sourcemappingvalidationcontroller-begin) (POST)
- [Receipt](#sourcemappingvalidationcontroller-receipt) (GET)
- [Status](#sourcemappingvalidationcontroller-status) (GET)
- [Advance](#sourcemappingvalidationcontroller-advance) (POST)
- [Items](#sourcemappingvalidationcontroller-items) (GET)
- [Abandon](#sourcemappingvalidationcontroller-abandon) (POST)
- [Get](#sourcereaderselectioncontroller-get) (GET)
- [Replace](#sourcereaderselectioncontroller-replace) (PUT)
- [Capabilities](#filebatchcontroller-capabilities) (GET)
- [Create](#filebatchcontroller-create) (POST)
- [List](#filebatchcontroller-list) (GET)
- [Get](#filebatchcontroller-get) (GET)
- [Items](#filebatchcontroller-items) (GET)
- [Content](#filebatchcontroller-content) (PUT)
- [Receipt](#filebatchcontroller-receipt) (GET)
- [Submit](#filebatchcontroller-submit) (POST)
- [Cancel](#filebatchcontroller-cancel) (POST)
- [Reconcile](#filebatchcontroller-reconcile) (POST)
- [Recover original](#filebatchcontroller-recover-original) (POST)
- [Processing recovery](#filebatchcontroller-processing-recovery) (GET)
- [Recover processing](#filebatchcontroller-recover-processing) (POST)
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
- [Versions read](#documenthistoryreadcontroller-versions-read) (POST)
- [Version read](#documenthistoryreadcontroller-version-read) (POST)
- [Extractions read](#documenthistoryreadcontroller-extractions-read) (POST)
- [Parts read](#documenthistoryreadcontroller-parts-read) (POST)
- [Part read](#documenthistoryreadcontroller-part-read) (POST)
- [Original read](#documenthistoryreadcontroller-original-read) (POST)
- [Snapshot](#tableprovenancecontroller-snapshot) (GET)
- [History](#tableprovenancecontroller-history) (GET)
- [Manifest](#tablecoordinatecontroller-manifest) (GET)
- [Cells](#tablecoordinatecontroller-cells) (POST)
- [Rows](#tablecoordinatecontroller-rows) (GET)
- [Columns](#tablecoordinatecontroller-columns) (GET)
- [Snapshot read](#tableprovenancereadcontroller-snapshot-read) (POST)
- [History read](#tableprovenancereadcontroller-history-read) (POST)
- [Manifest read](#tableprovenancereadcontroller-manifest-read) (POST)
- [Rows read](#tableprovenancereadcontroller-rows-read) (POST)
- [Columns read](#tableprovenancereadcontroller-columns-read) (POST)
- [Schema read](#knowledgereadcontroller-schema-read) (POST)
- [Lineage read](#knowledgereadcontroller-lineage-read) (POST)
- [Document chunks read](#knowledgereadcontroller-document-chunks-read) (POST)
- [Document original read](#knowledgereadcontroller-document-original-read) (POST)

<!-- operation: SourceCapabilitiesController.get -->
<a id="sourcecapabilitiescontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/content-sources/capabilities
```

Contract operation: `SourceCapabilitiesController.get`.

| SDK | Method |
| --- | --- |
| Python | `source_capabilities` |
| TypeScript | `contentSources.capabilities` |
| Java | `client.contentSources.capabilities` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceCapabilitiesOutput`](../models/sourcecapabilitiesoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentConnectionsController.list -->
<a id="contentconnectionscontroller-list"></a>
## List

```http
GET /api/v1/tenants/{tenant_id}/content-sources/connections
```

Contract operation: `ContentConnectionsController.list`.

| SDK | Method |
| --- | --- |
| Python | `source_connections` |
| TypeScript | `contentSources.list` |
| Java | `client.contentSources.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `cursor` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `limit` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceConnectionPage`](../models/sourceconnectionpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentConnectionsController.get -->
<a id="contentconnectionscontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/content-sources/connections/{connection_id}
```

Contract operation: `ContentConnectionsController.get`.

| SDK | Method |
| --- | --- |
| Python | `source_connection` |
| TypeScript | `contentSources.get` |
| Java | `client.contentSources.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `connection_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceConnectionOutput`](../models/sourceconnectionoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentConnectionsController.disconnect -->
<a id="contentconnectionscontroller-disconnect"></a>
## Disconnect

```http
POST /api/v1/tenants/{tenant_id}/content-sources/connections/{connection_id}/disconnect
```

Contract operation: `ContentConnectionsController.disconnect`.

| SDK | Method |
| --- | --- |
| Python | `disconnect_source_connection` |
| TypeScript | `contentSources.disconnect` |
| Java | `client.contentSources.disconnect` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `connection_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceConnectionRevision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceConnectionRevision`](../models/sourceconnectionrevision.md) |
| Response schema | [`SourceConnectionOutput`](../models/sourceconnectionoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentConnectionsController.sites -->
<a id="contentconnectionscontroller-sites"></a>
## Sites

```http
GET /api/v1/tenants/{tenant_id}/content-sources/connections/{connection_id}/sites
```

Contract operation: `ContentConnectionsController.sites`.

| SDK | Method |
| --- | --- |
| Python | `source_sites` |
| TypeScript | `contentSources.sites` |
| Java | `client.contentSources.sites` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `connection_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | Yes | Not specified |
| `cursor` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceLocationPage`](../models/sourcelocationpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentConnectionsController.drives -->
<a id="contentconnectionscontroller-drives"></a>
## Drives

```http
GET /api/v1/tenants/{tenant_id}/content-sources/connections/{connection_id}/drives
```

Contract operation: `ContentConnectionsController.drives`.

| SDK | Method |
| --- | --- |
| Python | `source_drives` |
| TypeScript | `contentSources.drives` |
| Java | `client.contentSources.drives` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `connection_id` | path | `PathVar[str]` | Yes | Not specified |
| `site_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `cursor` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceLocationPage`](../models/sourcelocationpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContentConnectionsController.children -->
<a id="contentconnectionscontroller-children"></a>
## Children

```http
GET /api/v1/tenants/{tenant_id}/content-sources/connections/{connection_id}/children
```

Contract operation: `ContentConnectionsController.children`.

| SDK | Method |
| --- | --- |
| Python | `source_children` |
| TypeScript | `contentSources.children` |
| Java | `client.contentSources.children` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `connection_id` | path | `PathVar[str]` | Yes | Not specified |
| `drive_id` | query | `QueryParam[str]` | Yes | Not specified |
| `folder_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `cursor` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceFolderPage`](../models/sourcefolderpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.mappings_page -->
<a id="sourcemappingcontroller-mappings-page"></a>
## Mappings page

```http
GET /api/v1/tenants/{tenant_id}/content-sources/mappings
```

Contract operation: `SourceMappingController.mappings_page`.

| SDK | Method |
| --- | --- |
| Python | `source_mappings` |
| TypeScript | `contentSources.mappings` |
| Java | `client.contentSources.mappings` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `limit` | query | `QueryParam[int]` | No | `25` |
| `cursor` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceMappingPage`](../models/sourcemappingpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.get -->
<a id="sourcemappingcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/content-sources/mappings/{mapping_id}
```

Contract operation: `SourceMappingController.get`.

| SDK | Method |
| --- | --- |
| Python | `source_mapping` |
| TypeScript | `contentSources.mapping` |
| Java | `client.contentSources.mapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceMappingOutput`](../models/sourcemappingoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.runs -->
<a id="sourcemappingcontroller-runs"></a>
## Runs

```http
GET /api/v1/tenants/{tenant_id}/content-sources/mappings/{mapping_id}/runs
```

Contract operation: `SourceMappingController.runs`.

| SDK | Method |
| --- | --- |
| Python | `source_mapping_runs` |
| TypeScript | `contentSources.runs` |
| Java | `client.contentSources.runs` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
| `limit` | query | `QueryParam[int]` | No | `25` |
| `cursor` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceRunPage`](../models/sourcerunpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.initial_operation -->
<a id="sourcemappingcontroller-initial-operation"></a>
## Initial operation

```http
GET /api/v1/tenants/{tenant_id}/content-sources/operations/{operation_id}
```

Contract operation: `SourceMappingController.initial_operation`.

| SDK | Method |
| --- | --- |
| Python | `source_initial_operation` |
| TypeScript | `contentSources.initialOperation` |
| Java | `client.contentSources.initialOperation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `operation_id` | path | `PathVar[str]` | Yes | Not specified |
| `action` | query | `QueryParam[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceOperationReceipt`](../models/sourceoperationreceipt.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.operation -->
<a id="sourcemappingcontroller-operation"></a>
## Operation

```http
GET /api/v1/tenants/{tenant_id}/content-sources/mappings/{mapping_id}/operations/{operation_id}
```

Contract operation: `SourceMappingController.operation`.

| SDK | Method |
| --- | --- |
| Python | `source_operation` |
| TypeScript | `contentSources.operation` |
| Java | `client.contentSources.operation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
| `operation_id` | path | `PathVar[str]` | Yes | Not specified |
| `action` | query | `QueryParam[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceOperationReceipt`](../models/sourceoperationreceipt.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.run -->
<a id="sourcemappingcontroller-run"></a>
## Run

```http
GET /api/v1/tenants/{tenant_id}/content-sources/runs/{run_id}
```

Contract operation: `SourceMappingController.run`.

| SDK | Method |
| --- | --- |
| Python | `source_run` |
| TypeScript | `contentSources.run` |
| Java | `client.contentSources.run` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceRunOutput`](../models/sourcerunoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.run_items -->
<a id="sourcemappingcontroller-run-items"></a>
## Run items

```http
GET /api/v1/tenants/{tenant_id}/content-sources/runs/{run_id}/items
```

Contract operation: `SourceMappingController.run_items`.

| SDK | Method |
| --- | --- |
| Python | `source_run_items` |
| TypeScript | `contentSources.runItems` |
| Java | `client.contentSources.runItems` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |
| `limit` | query | `QueryParam[int]` | No | `25` |
| `cursor` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceRunItemPage`](../models/sourcerunitempage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.cancel -->
<a id="sourcemappingcontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/content-sources/runs/{run_id}/cancel
```

Contract operation: `SourceMappingController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_source_run` |
| TypeScript | `contentSources.cancelRun` |
| Java | `client.contentSources.cancelRun` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceControlInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceControlInput`](../models/sourcecontrolinput.md) |
| Response schema | [`SourceControlOutput`](../models/sourcecontroloutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.retry -->
<a id="sourcemappingcontroller-retry"></a>
## Retry

```http
POST /api/v1/tenants/{tenant_id}/content-sources/runs/{run_id}/retry
```

Contract operation: `SourceMappingController.retry`.

| SDK | Method |
| --- | --- |
| Python | `retry_source_run` |
| TypeScript | `contentSources.retryRun` |
| Java | `client.contentSources.retryRun` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceControlInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceControlInput`](../models/sourcecontrolinput.md) |
| Response schema | [`SourceControlOutput`](../models/sourcecontroloutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.review -->
<a id="sourcemappingcontroller-review"></a>
## Review

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mapping-reviews
```

Contract operation: `SourceMappingController.review`.

| SDK | Method |
| --- | --- |
| Python | `review_source_mapping` |
| TypeScript | `contentSources.reviewMapping` |
| Java | `client.contentSources.reviewMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourcePolicyReviewInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourcePolicyReviewInput`](../models/sourcepolicyreviewinput.md) |
| Response schema | [`SourcePolicyOperationOutput`](../models/sourcepolicyoperationoutput.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.items -->
<a id="sourcemappingcontroller-items"></a>
## Items

```http
GET /api/v1/tenants/{tenant_id}/content-sources/mapping-reviews/{review_id}/items
```

Contract operation: `SourceMappingController.items`.

| SDK | Method |
| --- | --- |
| Python | `source_review_items` |
| TypeScript | `contentSources.reviewItems` |
| Java | `client.contentSources.reviewItems` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `review_id` | path | `PathVar[str]` | Yes | Not specified |
| `limit` | query | `QueryParam[int]` | No | `25` |
| `cursor` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceReviewPage`](../models/sourcereviewpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.create -->
<a id="sourcemappingcontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mappings
```

Contract operation: `SourceMappingController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_source_mapping` |
| TypeScript | `contentSources.createMapping` |
| Java | `client.contentSources.createMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourcePolicyApplyInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourcePolicyApplyInput`](../models/sourcepolicyapplyinput.md) |
| Response schema | [`SourcePolicyOperationOutput`](../models/sourcepolicyoperationoutput.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.revise -->
<a id="sourcemappingcontroller-revise"></a>
## Revise

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mappings/{mapping_id}/reviews
```

Contract operation: `SourceMappingController.revise`.

| SDK | Method |
| --- | --- |
| Python | `revise_source_mapping` |
| TypeScript | `contentSources.reviseMapping` |
| Java | `client.contentSources.reviseMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceExistingPolicyReviewInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceExistingPolicyReviewInput`](../models/sourceexistingpolicyreviewinput.md) |
| Response schema | [`SourcePolicyOperationOutput`](../models/sourcepolicyoperationoutput.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.apply -->
<a id="sourcemappingcontroller-apply"></a>
## Apply

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mappings/{mapping_id}/apply
```

Contract operation: `SourceMappingController.apply`.

| SDK | Method |
| --- | --- |
| Python | `apply_source_mapping` |
| TypeScript | `contentSources.applyMapping` |
| Java | `client.contentSources.applyMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourcePolicyApplyInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourcePolicyApplyInput`](../models/sourcepolicyapplyinput.md) |
| Response schema | [`SourcePolicyOperationOutput`](../models/sourcepolicyoperationoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.sync -->
<a id="sourcemappingcontroller-sync"></a>
## Sync

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mappings/{mapping_id}/sync
```

Contract operation: `SourceMappingController.sync`.

| SDK | Method |
| --- | --- |
| Python | `sync_source_mapping` |
| TypeScript | `contentSources.syncMapping` |
| Java | `client.contentSources.syncMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceControlInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceControlInput`](../models/sourcecontrolinput.md) |
| Response schema | [`SourceControlOutput`](../models/sourcecontroloutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.pause -->
<a id="sourcemappingcontroller-pause"></a>
## Pause

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mappings/{mapping_id}/pause
```

Contract operation: `SourceMappingController.pause`.

| SDK | Method |
| --- | --- |
| Python | `pause_source_mapping` |
| TypeScript | `contentSources.pauseMapping` |
| Java | `client.contentSources.pauseMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceControlInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceControlInput`](../models/sourcecontrolinput.md) |
| Response schema | [`SourceControlOutput`](../models/sourcecontroloutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.resume -->
<a id="sourcemappingcontroller-resume"></a>
## Resume

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mappings/{mapping_id}/resume
```

Contract operation: `SourceMappingController.resume`.

| SDK | Method |
| --- | --- |
| Python | `resume_source_mapping` |
| TypeScript | `contentSources.resumeMapping` |
| Java | `client.contentSources.resumeMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceControlInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceControlInput`](../models/sourcecontrolinput.md) |
| Response schema | [`SourceControlOutput`](../models/sourcecontroloutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingController.retire -->
<a id="sourcemappingcontroller-retire"></a>
## Retire

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mappings/{mapping_id}/retire
```

Contract operation: `SourceMappingController.retire`.

| SDK | Method |
| --- | --- |
| Python | `retire_source_mapping` |
| TypeScript | `contentSources.retireMapping` |
| Java | `client.contentSources.retireMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceControlInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceControlInput`](../models/sourcecontrolinput.md) |
| Response schema | [`SourceControlOutput`](../models/sourcecontroloutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingValidationController.begin -->
<a id="sourcemappingvalidationcontroller-begin"></a>
## Begin

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mapping-validations
```

Contract operation: `SourceMappingValidationController.begin`.

| SDK | Method |
| --- | --- |
| Python | `begin_source_mapping_validation` |
| TypeScript | `contentSources.beginValidation` |
| Java | `client.contentSources.beginValidation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceMappingValidationInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceMappingValidationInput`](../models/sourcemappingvalidationinput.md) |
| Response schema | [`SourceMappingValidationOutput`](../models/sourcemappingvalidationoutput.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingValidationController.receipt -->
<a id="sourcemappingvalidationcontroller-receipt"></a>
## Receipt

```http
GET /api/v1/tenants/{tenant_id}/content-sources/mapping-validations/operations/{operation_id}
```

Contract operation: `SourceMappingValidationController.receipt`.

| SDK | Method |
| --- | --- |
| Python | `source_mapping_validation_receipt` |
| TypeScript | `contentSources.validationReceipt` |
| Java | `client.contentSources.validationReceipt` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `operation_id` | path | `PathVar[UUID]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceMappingValidationOutput`](../models/sourcemappingvalidationoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingValidationController.status -->
<a id="sourcemappingvalidationcontroller-status"></a>
## Status

```http
GET /api/v1/tenants/{tenant_id}/content-sources/mapping-validations/{validation_id}
```

Contract operation: `SourceMappingValidationController.status`.

| SDK | Method |
| --- | --- |
| Python | `source_mapping_validation` |
| TypeScript | `contentSources.validation` |
| Java | `client.contentSources.validation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `validation_id` | path | `PathVar[UUID]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceMappingValidationOutput`](../models/sourcemappingvalidationoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingValidationController.advance -->
<a id="sourcemappingvalidationcontroller-advance"></a>
## Advance

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mapping-validations/{validation_id}/continue
```

Contract operation: `SourceMappingValidationController.advance`.

| SDK | Method |
| --- | --- |
| Python | `advance_source_mapping_validation` |
| TypeScript | `contentSources.advanceValidation` |
| Java | `client.contentSources.advanceValidation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `validation_id` | path | `PathVar[UUID]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceMappingValidationContinueInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceMappingValidationContinueInput`](../models/sourcemappingvalidationcontinueinput.md) |
| Response schema | [`SourceMappingValidationOutput`](../models/sourcemappingvalidationoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingValidationController.items -->
<a id="sourcemappingvalidationcontroller-items"></a>
## Items

```http
GET /api/v1/tenants/{tenant_id}/content-sources/mapping-validations/{validation_id}/items
```

Contract operation: `SourceMappingValidationController.items`.

| SDK | Method |
| --- | --- |
| Python | `source_mapping_validation_items` |
| TypeScript | `contentSources.validationItems` |
| Java | `client.contentSources.validationItems` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `validation_id` | path | `PathVar[UUID]` | Yes | Not specified |
| `cursor` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `limit` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SourceMappingValidationItemPage`](../models/sourcemappingvalidationitempage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceMappingValidationController.abandon -->
<a id="sourcemappingvalidationcontroller-abandon"></a>
## Abandon

```http
POST /api/v1/tenants/{tenant_id}/content-sources/mapping-validations/{validation_id}/abandon
```

Contract operation: `SourceMappingValidationController.abandon`.

| SDK | Method |
| --- | --- |
| Python | `abandon_source_mapping_validation` |
| TypeScript | `contentSources.abandonValidation` |
| Java | `client.contentSources.abandonValidation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `validation_id` | path | `PathVar[UUID]` | Yes | Not specified |
| `body` | body | `Valid[Body[SourceMappingValidationAbandonInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SourceMappingValidationAbandonInput`](../models/sourcemappingvalidationabandoninput.md) |
| Response schema | [`SourceMappingValidationOutput`](../models/sourcemappingvalidationoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceReaderSelectionController.get -->
<a id="sourcereaderselectioncontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/content-sources/reader-selection
```

Contract operation: `SourceReaderSelectionController.get`.

| SDK | Method |
| --- | --- |
| Python | `reader_source_selection` |
| TypeScript | `contentSources.readerSelection` |
| Java | `client.contentSources.readerSelection` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ReaderSelectionOutput`](../models/readerselectionoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: SourceReaderSelectionController.replace -->
<a id="sourcereaderselectioncontroller-replace"></a>
## Replace

```http
PUT /api/v1/tenants/{tenant_id}/content-sources/reader-selection
```

Contract operation: `SourceReaderSelectionController.replace`.

| SDK | Method |
| --- | --- |
| Python | `replace_reader_source_selection` |
| TypeScript | `contentSources.replaceReaderSelection` |
| Java | `client.contentSources.replaceReaderSelection` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ReaderSelectionInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ReaderSelectionInput`](../models/readerselectioninput.md) |
| Response schema | [`ReaderSelectionOutput`](../models/readerselectionoutput.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.capabilities -->
<a id="filebatchcontroller-capabilities"></a>
## Capabilities

```http
GET /api/v1/tenants/{tenant_id}/source-batch-capabilities
```

Contract operation: `FileBatchController.capabilities`.

| SDK | Method |
| --- | --- |
| Python | `file_batch_capabilities` |
| TypeScript | `fileBatches.capabilities` |
| Java | `client.fileBatches.capabilities` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | `QueryParam[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`FileBatchCapabilities`](../models/filebatchcapabilities.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.create -->
<a id="filebatchcontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/sources/batches
```

Contract operation: `FileBatchController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_file_batch` |
| TypeScript | `fileBatches.create` |
| Java | `client.fileBatches.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[FileBatchCreate]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`FileBatchCreate`](../models/filebatchcreate.md) |
| Response schema | [`FileBatchView`](../models/filebatchview.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.list -->
<a id="filebatchcontroller-list"></a>
## List

```http
GET /api/v1/tenants/{tenant_id}/sources/batches
```

Contract operation: `FileBatchController.list`.

| SDK | Method |
| --- | --- |
| Python | `file_batches` |
| TypeScript | `fileBatches.list` |
| Java | `client.fileBatches.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`FileBatchPage`](../models/filebatchpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.get -->
<a id="filebatchcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}
```

Contract operation: `FileBatchController.get`.

| SDK | Method |
| --- | --- |
| Python | `file_batch` |
| TypeScript | `fileBatches.get` |
| Java | `client.fileBatches.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`FileBatchView`](../models/filebatchview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.items -->
<a id="filebatchcontroller-items"></a>
## Items

```http
GET /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}/items
```

Contract operation: `FileBatchController.items`.

| SDK | Method |
| --- | --- |
| Python | `file_batch_items` |
| TypeScript | `fileBatches.items` |
| Java | `client.fileBatches.items` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`FileItemPage`](../models/fileitempage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.content -->
<a id="filebatchcontroller-content"></a>
## Content

```http
PUT /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}/items/{item_id}/content
```

Contract operation: `FileBatchController.content`.

| SDK | Method |
| --- | --- |
| Python | `upload_file_batch_item` |
| TypeScript | `fileBatches.upload` |
| Java | `client.fileBatches.upload` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `item_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`BulkFileUpload`](../models/bulkfileupload.md) |
| Response schema | [`StagedFileReceipt`](../models/stagedfilereceipt.md) |
| Success status | `200` |
| Declared encoding | `application/octet-stream` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.receipt -->
<a id="filebatchcontroller-receipt"></a>
## Receipt

```http
GET /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}/items/{item_id}/receipt
```

Contract operation: `FileBatchController.receipt`.

| SDK | Method |
| --- | --- |
| Python | `file_batch_item_receipt` |
| TypeScript | `fileBatches.receipt` |
| Java | `client.fileBatches.receipt` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `item_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`StagedFileReceipt`](../models/stagedfilereceipt.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.submit -->
<a id="filebatchcontroller-submit"></a>
## Submit

```http
POST /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}/submit
```

Contract operation: `FileBatchController.submit`.

| SDK | Method |
| --- | --- |
| Python | `submit_file_batch` |
| TypeScript | `fileBatches.submit` |
| Java | `client.fileBatches.submit` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[BulkAction]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`BulkAction`](../models/bulkaction.md) |
| Response schema | [`FileBatchView`](../models/filebatchview.md) |
| Success status | `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.cancel -->
<a id="filebatchcontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}/cancel
```

Contract operation: `FileBatchController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_file_batch` |
| TypeScript | `fileBatches.cancel` |
| Java | `client.fileBatches.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[BulkAction]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`BulkAction`](../models/bulkaction.md) |
| Response schema | [`FileBatchView`](../models/filebatchview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.reconcile -->
<a id="filebatchcontroller-reconcile"></a>
## Reconcile

```http
POST /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}/items/{item_id}/reconcile
```

Contract operation: `FileBatchController.reconcile`.

| SDK | Method |
| --- | --- |
| Python | `reconcile_file_batch_item` |
| TypeScript | `fileBatches.reconcile` |
| Java | `client.fileBatches.reconcile` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `item_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[BulkAction]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`BulkAction`](../models/bulkaction.md) |
| Response schema | [`FileBatchView`](../models/filebatchview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.recover_original -->
<a id="filebatchcontroller-recover-original"></a>
## Recover original

```http
POST /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}/items/{item_id}/original/reconcile
```

Contract operation: `FileBatchController.recover_original`.

| SDK | Method |
| --- | --- |
| Python | `reconcile_file_batch_original` |
| TypeScript | `fileBatches.recoverOriginal` |
| Java | `client.fileBatches.recoverOriginal` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `item_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[BulkAction]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`BulkAction`](../models/bulkaction.md) |
| Response schema | [`FileBatchView`](../models/filebatchview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.processing_recovery -->
<a id="filebatchcontroller-processing-recovery"></a>
## Processing recovery

```http
GET /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}/items/{item_id}/recovery
```

Contract operation: `FileBatchController.processing_recovery`.

| SDK | Method |
| --- | --- |
| Python | `file_batch_processing_recovery` |
| TypeScript | `fileBatches.processingRecovery` |
| Java | `client.fileBatches.processingRecovery` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `item_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`FileRecoveryView`](../models/filerecoveryview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: FileBatchController.recover_processing -->
<a id="filebatchcontroller-recover-processing"></a>
## Recover processing

```http
POST /api/v1/tenants/{tenant_id}/sources/batches/{batch_id}/items/{item_id}/recover
```

Contract operation: `FileBatchController.recover_processing`.

| SDK | Method |
| --- | --- |
| Python | `recover_file_batch_processing` |
| TypeScript | `fileBatches.recoverProcessing` |
| Java | `client.fileBatches.recoverProcessing` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `item_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[BulkRecoveryAction]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`BulkRecoveryAction`](../models/bulkrecoveryaction.md) |
| Response schema | [`FileBatchView`](../models/filebatchview.md) |
| Success status | `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

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

<!-- operation: DocumentHistoryReadController.versions_read -->
<a id="documenthistoryreadcontroller-versions-read"></a>
## Versions read

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/read
```

Contract operation: `DocumentHistoryReadController.versions_read`.

| SDK | Method |
| --- | --- |
| Python | `read_document_versions` |
| TypeScript | `documents.readVersions` |
| Java | `client.documents.readVersions` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ReaderPageInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ReaderPageInput`](../models/readerpageinput.md) |
| Response schema | [`DocumentVersionPage`](../models/documentversionpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryReadController.version_read -->
<a id="documenthistoryreadcontroller-version-read"></a>
## Version read

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}/read
```

Contract operation: `DocumentHistoryReadController.version_read`.

| SDK | Method |
| --- | --- |
| Python | `read_document_version` |
| TypeScript | `documents.readVersion` |
| Java | `client.documents.readVersion` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ReaderReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ReaderReadInput`](../models/readerreadinput.md) |
| Response schema | [`DocumentVersion`](../models/documentversion.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryReadController.extractions_read -->
<a id="documenthistoryreadcontroller-extractions-read"></a>
## Extractions read

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}/extractions/read
```

Contract operation: `DocumentHistoryReadController.extractions_read`.

| SDK | Method |
| --- | --- |
| Python | `read_document_extractions` |
| TypeScript | `documents.readExtractions` |
| Java | `client.documents.readExtractions` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ReaderPageInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ReaderPageInput`](../models/readerpageinput.md) |
| Response schema | [`DocumentExtractionPage`](../models/documentextractionpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryReadController.parts_read -->
<a id="documenthistoryreadcontroller-parts-read"></a>
## Parts read

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}/extractions/{extraction_id}/parts/read
```

Contract operation: `DocumentHistoryReadController.parts_read`.

| SDK | Method |
| --- | --- |
| Python | `read_document_parts` |
| TypeScript | `documents.readParts` |
| Java | `client.documents.readParts` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |
| `extraction_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[DocumentPartsReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`DocumentPartsReadInput`](../models/documentpartsreadinput.md) |
| Response schema | [`DocumentPartPage`](../models/documentpartpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryReadController.part_read -->
<a id="documenthistoryreadcontroller-part-read"></a>
## Part read

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}/extractions/{extraction_id}/parts/{source_part_id}/read
```

Contract operation: `DocumentHistoryReadController.part_read`.

| SDK | Method |
| --- | --- |
| Python | `read_document_part` |
| TypeScript | `documents.readPart` |
| Java | `client.documents.readPart` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |
| `extraction_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_part_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ReaderReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ReaderReadInput`](../models/readerreadinput.md) |
| Response schema | [`DocumentPartContent`](../models/documentpartcontent.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: DocumentHistoryReadController.original_read -->
<a id="documenthistoryreadcontroller-original-read"></a>
## Original read

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/versions/{source_version_id}/original/read
```

Contract operation: `DocumentHistoryReadController.original_read`.

| SDK | Method |
| --- | --- |
| Python | `read_document_version_original` |
| TypeScript | `documents.readVersionOriginal` |
| Java | `client.documents.readVersionOriginal` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `source_version_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ReaderReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ReaderReadInput`](../models/readerreadinput.md) |
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

<!-- operation: TableProvenanceReadController.snapshot_read -->
<a id="tableprovenancereadcontroller-snapshot-read"></a>
## Snapshot read

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/provenance/read
```

Contract operation: `TableProvenanceReadController.snapshot_read`.

| SDK | Method |
| --- | --- |
| Python | `read_table_provenance` |
| TypeScript | `dataset.readTableProvenance` |
| Java | `client.datasets.readTableProvenance` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SnapshotReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SnapshotReadInput`](../models/snapshotreadinput.md) |
| Response schema | [`TableProvenance`](../models/tableprovenance.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableProvenanceReadController.history_read -->
<a id="tableprovenancereadcontroller-history-read"></a>
## History read

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/snapshots/read
```

Contract operation: `TableProvenanceReadController.history_read`.

| SDK | Method |
| --- | --- |
| Python | `read_table_snapshots` |
| TypeScript | `dataset.readTableSnapshots` |
| Java | `client.datasets.readTableSnapshots` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SnapshotHistoryReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SnapshotHistoryReadInput`](../models/snapshothistoryreadinput.md) |
| Response schema | [`TableSnapshotReadPage`](../models/tablesnapshotreadpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableProvenanceReadController.manifest_read -->
<a id="tableprovenancereadcontroller-manifest-read"></a>
## Manifest read

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates/read
```

Contract operation: `TableProvenanceReadController.manifest_read`.

| SDK | Method |
| --- | --- |
| Python | `read_table_coordinates` |
| TypeScript | `dataset.readTableCoordinates` |
| Java | `client.datasets.readTableCoordinates` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SnapshotReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SnapshotReadInput`](../models/snapshotreadinput.md) |
| Response schema | [`TableCoordinateManifest`](../models/tablecoordinatemanifest.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableProvenanceReadController.rows_read -->
<a id="tableprovenancereadcontroller-rows-read"></a>
## Rows read

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates/rows/read
```

Contract operation: `TableProvenanceReadController.rows_read`.

| SDK | Method |
| --- | --- |
| Python | `read_table_coordinate_rows` |
| TypeScript | `dataset.readTableCoordinateRows` |
| Java | `client.datasets.readTableCoordinateRows` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SnapshotPageReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SnapshotPageReadInput`](../models/snapshotpagereadinput.md) |
| Response schema | [`TableRowRangePage`](../models/tablerowrangepage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: TableProvenanceReadController.columns_read -->
<a id="tableprovenancereadcontroller-columns-read"></a>
## Columns read

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates/columns/read
```

Contract operation: `TableProvenanceReadController.columns_read`.

| SDK | Method |
| --- | --- |
| Python | `read_table_coordinate_columns` |
| TypeScript | `dataset.readTableCoordinateColumns` |
| Java | `client.datasets.readTableCoordinateColumns` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `table_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SnapshotPageReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SnapshotPageReadInput`](../models/snapshotpagereadinput.md) |
| Response schema | [`TableColumnBindingPage`](../models/tablecolumnbindingpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeReadController.schema_read -->
<a id="knowledgereadcontroller-schema-read"></a>
## Schema read

```http
POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/schema/read
```

Contract operation: `KnowledgeReadController.schema_read`.

| SDK | Method |
| --- | --- |
| Python | `read_dataset_schema` |
| TypeScript | `dataset.readSchema` |
| Java | `client.datasets.readSchema` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `dataset_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ReaderReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ReaderReadInput`](../models/readerreadinput.md) |
| Response schema | [`DatasetSchema`](../models/datasetschema.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeReadController.lineage_read -->
<a id="knowledgereadcontroller-lineage-read"></a>
## Lineage read

```http
POST /api/v1/tenants/{tenant_id}/lineage/read
```

Contract operation: `KnowledgeReadController.lineage_read`.

| SDK | Method |
| --- | --- |
| Python | `read_lineage` |
| TypeScript | `readLineage` |
| Java | `client.knowledge.readLineage` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[LineageReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`LineageReadInput`](../models/lineagereadinput.md) |
| Response schema | [`Lineage`](../models/lineage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeReadController.document_chunks_read -->
<a id="knowledgereadcontroller-document-chunks-read"></a>
## Document chunks read

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/chunks/read
```

Contract operation: `KnowledgeReadController.document_chunks_read`.

| SDK | Method |
| --- | --- |
| Python | `read_document_chunks` |
| TypeScript | `documents.readChunks` |
| Java | `client.documents.readChunks` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[DocumentChunksReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`DocumentChunksReadInput`](../models/documentchunksreadinput.md) |
| Response schema | [`DocumentChunks`](../models/documentchunks.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeReadController.document_original_read -->
<a id="knowledgereadcontroller-document-original-read"></a>
## Document original read

```http
POST /api/v1/tenants/{tenant_id}/documents/{document_id}/original/read
```

Contract operation: `KnowledgeReadController.document_original_read`.

| SDK | Method |
| --- | --- |
| Python | `read_document_original` |
| TypeScript | `documents.readOriginal` |
| Java | `client.documents.readOriginal` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `document_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ReaderReadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ReaderReadInput`](../models/readerreadinput.md) |
| Response schema | [`BinaryDownload`](../models/binarydownload.md) |
| Success status | `200` |
| Declared encoding | `binary` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
