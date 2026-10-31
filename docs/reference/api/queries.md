<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Search and queries

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Search](#knowledgecontroller-search) (POST)
- [Query](#knowledgecontroller-query) (POST)

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
