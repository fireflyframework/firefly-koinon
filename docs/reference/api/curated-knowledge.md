<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Curated knowledge

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Preview](#curatedknowledgecontroller-preview) (POST)
- [Intent](#curatedknowledgecontroller-intent) (GET)
- [Confirm](#curatedknowledgecontroller-confirm) (POST)
- [Cancel](#curatedknowledgecontroller-cancel) (POST)
- [List](#curatedknowledgecontroller-list) (GET)
- [Get](#curatedknowledgecontroller-get) (GET)
- [Version](#curatedknowledgecontroller-version) (GET)

<!-- operation: CuratedKnowledgeController.preview -->
<a id="curatedknowledgecontroller-preview"></a>
## Preview

```http
POST /api/v1/tenants/{tenant_id}/knowledge-intents
```

Contract operation: `CuratedKnowledgeController.preview`.

| SDK | Method |
| --- | --- |
| Python | `preview_knowledge` |
| TypeScript | `knowledgeIntents.preview` |
| Java | `client.knowledgeIntents.preview` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[KnowledgeIntentInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`KnowledgeIntentInput`](../models/knowledgeintentinput.md) |
| Response schema | [`KnowledgeIntent`](../models/knowledgeintent.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CuratedKnowledgeController.intent -->
<a id="curatedknowledgecontroller-intent"></a>
## Intent

```http
GET /api/v1/tenants/{tenant_id}/knowledge-intents/{intent_id}
```

Contract operation: `CuratedKnowledgeController.intent`.

| SDK | Method |
| --- | --- |
| Python | `knowledge_intent` |
| TypeScript | `knowledgeIntents.get` |
| Java | `client.knowledgeIntents.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `intent_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`KnowledgeIntent`](../models/knowledgeintent.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CuratedKnowledgeController.confirm -->
<a id="curatedknowledgecontroller-confirm"></a>
## Confirm

```http
POST /api/v1/tenants/{tenant_id}/knowledge-intents/{intent_id}/confirm
```

Contract operation: `CuratedKnowledgeController.confirm`.

| SDK | Method |
| --- | --- |
| Python | `confirm_knowledge` |
| TypeScript | `knowledgeIntents.confirm` |
| Java | `client.knowledgeIntents.confirm` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `intent_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[KnowledgeConfirmation]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`KnowledgeConfirmation`](../models/knowledgeconfirmation.md) |
| Response schema | [`KnowledgeCommitOutcome`](../models/knowledgecommitoutcome.md) |
| Success status | `200`, `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CuratedKnowledgeController.cancel -->
<a id="curatedknowledgecontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/knowledge-intents/{intent_id}/cancel
```

Contract operation: `CuratedKnowledgeController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_knowledge` |
| TypeScript | `knowledgeIntents.cancel` |
| Java | `client.knowledgeIntents.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `intent_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[KnowledgeCancellation]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`KnowledgeCancellation`](../models/knowledgecancellation.md) |
| Response schema | [`KnowledgeIntent`](../models/knowledgeintent.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CuratedKnowledgeController.list -->
<a id="curatedknowledgecontroller-list"></a>
## List

```http
GET /api/v1/tenants/{tenant_id}/knowledge-items
```

Contract operation: `CuratedKnowledgeController.list`.

| SDK | Method |
| --- | --- |
| Python | `knowledge_items` |
| TypeScript | `knowledgeItems.list` |
| Java | `client.knowledgeItems.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `project_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `destination_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `q` | query | `QueryParam[str]` | No | `""` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`KnowledgeItemPage`](../models/knowledgeitempage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CuratedKnowledgeController.get -->
<a id="curatedknowledgecontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/knowledge-items/{item_id}
```

Contract operation: `CuratedKnowledgeController.get`.

| SDK | Method |
| --- | --- |
| Python | `knowledge_item` |
| TypeScript | `knowledgeItems.get` |
| Java | `client.knowledgeItems.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `item_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`KnowledgeItemView`](../models/knowledgeitemview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CuratedKnowledgeController.version -->
<a id="curatedknowledgecontroller-version"></a>
## Version

```http
GET /api/v1/tenants/{tenant_id}/knowledge-items/{item_id}/versions/{version}
```

Contract operation: `CuratedKnowledgeController.version`.

| SDK | Method |
| --- | --- |
| Python | `knowledge_version` |
| TypeScript | `knowledgeItems.version` |
| Java | `client.knowledgeItems.version` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `item_id` | path | `PathVar[str]` | Yes | Not specified |
| `version` | path | `PathVar[int]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`KnowledgeItemView`](../models/knowledgeitemview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
