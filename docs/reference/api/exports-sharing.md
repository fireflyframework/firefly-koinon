<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Exports and sharing

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Review](#exportcontroller-review) (POST)
- [Create](#exportcontroller-create) (POST)
- [List](#exportcontroller-list) (GET)
- [Get](#exportcontroller-get) (GET)
- [Download](#exportcontroller-download) (GET)
- [Cancel](#exportcontroller-cancel) (DELETE)
- [Review](#sharecontroller-review) (POST)
- [Create](#sharecontroller-create) (POST)
- [List](#sharecontroller-list) (GET)
- [Get](#sharecontroller-get) (GET)
- [Revoke](#sharecontroller-revoke) (DELETE)

<!-- operation: ExportController.review -->
<a id="exportcontroller-review"></a>
## Review

```http
POST /api/v1/tenants/{tenant_id}/exports/reviews
```

Contract operation: `ExportController.review`.

| SDK | Method |
| --- | --- |
| Python | `review_export` |
| TypeScript | `exports.review` |
| Java | `client.exports.review` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExportReviewRequest]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExportReviewRequest`](../models/exportreviewrequest.md) |
| Response schema | [`ExportReview`](../models/exportreview.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExportController.create -->
<a id="exportcontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/exports
```

Contract operation: `ExportController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_export` |
| TypeScript | `exports.create` |
| Java | `client.exports.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExportCreate]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExportCreate`](../models/exportcreate.md) |
| Response schema | [`Export`](../models/export.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExportController.list -->
<a id="exportcontroller-list"></a>
## List

```http
GET /api/v1/tenants/{tenant_id}/exports
```

Contract operation: `ExportController.list`.

| SDK | Method |
| --- | --- |
| Python | `exports` |
| TypeScript | `exports.list` |
| Java | `client.exports.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `status` | query | `QueryParam[str]` | No | `"all"` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ExportPage`](../models/exportpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExportController.get -->
<a id="exportcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/exports/{export_id}
```

Contract operation: `ExportController.get`.

| SDK | Method |
| --- | --- |
| Python | `export` |
| TypeScript | `exports.get` |
| Java | `client.exports.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `export_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Export`](../models/export.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExportController.download -->
<a id="exportcontroller-download"></a>
## Download

```http
GET /api/v1/tenants/{tenant_id}/exports/{export_id}/download
```

Contract operation: `ExportController.download`.

| SDK | Method |
| --- | --- |
| Python | `export_download` |
| TypeScript | `exports.download` |
| Java | `client.exports.download` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `export_id` | path | `PathVar[str]` | Yes | Not specified |

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

<!-- operation: ExportController.cancel -->
<a id="exportcontroller-cancel"></a>
## Cancel

```http
DELETE /api/v1/tenants/{tenant_id}/exports/{export_id}
```

Contract operation: `ExportController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_export` |
| TypeScript | `exports.cancel` |
| Java | `client.exports.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `export_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | No response body |
| Success status | `204` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ShareController.review -->
<a id="sharecontroller-review"></a>
## Review

```http
POST /api/v1/tenants/{tenant_id}/shares/reviews
```

Contract operation: `ShareController.review`.

| SDK | Method |
| --- | --- |
| Python | `review_share` |
| TypeScript | `shares.review` |
| Java | `client.shares.review` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ShareReviewInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ShareReviewInput`](../models/sharereviewinput.md) |
| Response schema | [`ShareReview`](../models/sharereview.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ShareController.create -->
<a id="sharecontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/shares
```

Contract operation: `ShareController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_share` |
| TypeScript | `shares.create` |
| Java | `client.shares.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ShareCreate]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ShareCreate`](../models/sharecreate.md) |
| Response schema | [`Share`](../models/share.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ShareController.list -->
<a id="sharecontroller-list"></a>
## List

```http
GET /api/v1/tenants/{tenant_id}/shares
```

Contract operation: `ShareController.list`.

| SDK | Method |
| --- | --- |
| Python | `shares` |
| TypeScript | `shares.list` |
| Java | `client.shares.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `status` | query | `QueryParam[str]` | No | `"all"` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SharePage`](../models/sharepage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ShareController.get -->
<a id="sharecontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/shares/{share_id}
```

Contract operation: `ShareController.get`.

| SDK | Method |
| --- | --- |
| Python | `share` |
| TypeScript | `shares.get` |
| Java | `client.shares.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `share_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SharedConversation`](../models/sharedconversation.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ShareController.revoke -->
<a id="sharecontroller-revoke"></a>
## Revoke

```http
DELETE /api/v1/tenants/{tenant_id}/shares/{share_id}
```

Contract operation: `ShareController.revoke`.

| SDK | Method |
| --- | --- |
| Python | `revoke_share` |
| TypeScript | `shares.revoke` |
| Java | `client.shares.revoke` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `share_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | No response body |
| Success status | `204` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
