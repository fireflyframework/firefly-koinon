<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Search and queries

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Capabilities](#querybatchcontroller-capabilities) (GET)
- [Create](#querybatchcontroller-create) (POST)
- [List](#querybatchcontroller-list) (GET)
- [Get](#querybatchcontroller-get) (GET)
- [Items](#querybatchcontroller-items) (GET)
- [Result](#querybatchcontroller-result) (GET)
- [Cancel](#querybatchcontroller-cancel) (POST)
- [Reconcile](#querybatchcontroller-reconcile) (POST)
- [Search](#knowledgecontroller-search) (POST)
- [Query](#knowledgecontroller-query) (POST)

<!-- operation: QueryBatchController.capabilities -->
<a id="querybatchcontroller-capabilities"></a>
## Capabilities

```http
GET /api/v1/tenants/{tenant_id}/query-batch-capabilities
```

Contract operation: `QueryBatchController.capabilities`.

| SDK | Method |
| --- | --- |
| Python | `query_batch_capabilities` |
| TypeScript | `queryBatches.capabilities` |
| Java | `client.queryBatches.capabilities` |

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
| Response schema | [`QueryBatchCapabilities`](../models/querybatchcapabilities.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: QueryBatchController.create -->
<a id="querybatchcontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/queries/batches
```

Contract operation: `QueryBatchController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_query_batch` |
| TypeScript | `queryBatches.create` |
| Java | `client.queryBatches.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[QueryBatchCreate]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`QueryBatchCreate`](../models/querybatchcreate.md) |
| Response schema | [`QueryBatchView`](../models/querybatchview.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: QueryBatchController.list -->
<a id="querybatchcontroller-list"></a>
## List

```http
GET /api/v1/tenants/{tenant_id}/queries/batches
```

Contract operation: `QueryBatchController.list`.

| SDK | Method |
| --- | --- |
| Python | `query_batches` |
| TypeScript | `queryBatches.list` |
| Java | `client.queryBatches.list` |

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
| Response schema | [`QueryBatchPage`](../models/querybatchpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: QueryBatchController.get -->
<a id="querybatchcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/queries/batches/{batch_id}
```

Contract operation: `QueryBatchController.get`.

| SDK | Method |
| --- | --- |
| Python | `query_batch` |
| TypeScript | `queryBatches.get` |
| Java | `client.queryBatches.get` |

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
| Response schema | [`QueryBatchView`](../models/querybatchview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: QueryBatchController.items -->
<a id="querybatchcontroller-items"></a>
## Items

```http
GET /api/v1/tenants/{tenant_id}/queries/batches/{batch_id}/items
```

Contract operation: `QueryBatchController.items`.

| SDK | Method |
| --- | --- |
| Python | `query_batch_items` |
| TypeScript | `queryBatches.items` |
| Java | `client.queryBatches.items` |

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
| Response schema | [`QueryBatchItemPage`](../models/querybatchitempage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: QueryBatchController.result -->
<a id="querybatchcontroller-result"></a>
## Result

```http
GET /api/v1/tenants/{tenant_id}/queries/batches/{batch_id}/items/{item_id}/result
```

Contract operation: `QueryBatchController.result`.

| SDK | Method |
| --- | --- |
| Python | `query_batch_result` |
| TypeScript | `queryBatches.result` |
| Java | `client.queryBatches.result` |

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
| Response schema | [`QueryBatchResult`](../models/querybatchresult.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: QueryBatchController.cancel -->
<a id="querybatchcontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/queries/batches/{batch_id}/cancel
```

Contract operation: `QueryBatchController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_query_batch` |
| TypeScript | `queryBatches.cancel` |
| Java | `client.queryBatches.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[QueryBatchAction]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`QueryBatchAction`](../models/querybatchaction.md) |
| Response schema | [`QueryBatchCancellation`](../models/querybatchcancellation.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: QueryBatchController.reconcile -->
<a id="querybatchcontroller-reconcile"></a>
## Reconcile

```http
POST /api/v1/tenants/{tenant_id}/queries/batches/{batch_id}/items/{item_id}/reconcile
```

Contract operation: `QueryBatchController.reconcile`.

| SDK | Method |
| --- | --- |
| Python | `reconcile_query_batch_item` |
| TypeScript | `queryBatches.reconcile` |
| Java | `client.queryBatches.reconcile` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `batch_id` | path | `PathVar[str]` | Yes | Not specified |
| `item_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[QueryBatchAction]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`QueryBatchAction`](../models/querybatchaction.md) |
| Response schema | [`QueryBatchView`](../models/querybatchview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeController.search -->
<a id="knowledgecontroller-search"></a>
## Search

```http
POST /api/v1/tenants/{tenant_id}/search
```

Contract operation: `KnowledgeController.search`.

| SDK | Method |
| --- | --- |
| Python | `search` |
| TypeScript | `search` |
| Java | `client.knowledge.search` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[SearchInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`SearchRequest`](../models/searchrequest.md) |
| Response schema | [`SearchResponse`](../models/searchresponse.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeController.query -->
<a id="knowledgecontroller-query"></a>
## Query

```http
POST /api/v1/tenants/{tenant_id}/query
```

Contract operation: `KnowledgeController.query`.

| SDK | Method |
| --- | --- |
| Python | `query` |
| TypeScript | `query` |
| Java | `client.knowledge.query` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[QueryInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`QueryRequest`](../models/queryrequest.md) |
| Response schema | [`QueryResponse`](../models/queryresponse.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
