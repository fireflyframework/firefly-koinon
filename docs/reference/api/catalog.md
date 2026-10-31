<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Catalog and proposals

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Catalog list](#catalogcontroller-catalog-list) (GET)
- [Catalog create](#catalogcontroller-catalog-create) (POST)
- [Catalog get](#catalogcontroller-catalog-get) (GET)
- [Catalog patch](#catalogcontroller-catalog-patch) (PATCH)
- [Catalog archive](#catalogcontroller-catalog-archive) (POST)
- [Catalog restore](#catalogcontroller-catalog-restore) (POST)
- [Catalog delete](#catalogcontroller-catalog-delete) (DELETE)
- [Get](#catalogproposalcontroller-get) (GET)
- [Confirm](#catalogproposalcontroller-confirm) (POST)
- [Cancel](#catalogproposalcontroller-cancel) (POST)

<!-- operation: CatalogController.catalog_list -->
<a id="catalogcontroller-catalog-list"></a>
## Catalog list

```http
GET /api/v1/tenants/{tenant_id}/catalog
```

Contract operation: `CatalogController.catalog_list`.

| SDK | Method |
| --- | --- |
| Python | `catalog` |
| TypeScript | `catalog.list` |
| Java | `client.catalog.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `kind` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `parent_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `project_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `include_archived` | query | `QueryParam[bool]` | No | `false` |
| `view` | query | `QueryParam[str]` | No | `"raw"` |
| `q` | query | `QueryParam[str]` | No | `""` |
| `status` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `format` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `tag` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `100` |
| `sort` | query | `QueryParam[str]` | No | `"name"` |
| `order` | query | `QueryParam[str]` | No | `"asc"` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[CatalogEntry]`](../models/page-catalogentry.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CatalogController.catalog_create -->
<a id="catalogcontroller-catalog-create"></a>
## Catalog create

```http
POST /api/v1/tenants/{tenant_id}/catalog
```

Contract operation: `CatalogController.catalog_create`.

| SDK | Method |
| --- | --- |
| Python | `create` |
| TypeScript | `catalog.create` |
| Java | `client.catalog.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[CatalogCreate]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`CatalogCreate`](../models/catalogcreate.md) |
| Response schema | [`CatalogEntry`](../models/catalogentry.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CatalogController.catalog_get -->
<a id="catalogcontroller-catalog-get"></a>
## Catalog get

```http
GET /api/v1/tenants/{tenant_id}/catalog/{entry_id}
```

Contract operation: `CatalogController.catalog_get`.

| SDK | Method |
| --- | --- |
| Python | `get` |
| TypeScript | `catalog.get` |
| Java | `client.catalog.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `entry_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`CatalogEntry`](../models/catalogentry.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CatalogController.catalog_patch -->
<a id="catalogcontroller-catalog-patch"></a>
## Catalog patch

```http
PATCH /api/v1/tenants/{tenant_id}/catalog/{entry_id}
```

Contract operation: `CatalogController.catalog_patch`.

| SDK | Method |
| --- | --- |
| Python | `update` |
| TypeScript | `catalog.update` |
| Java | `client.catalog.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `entry_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[CatalogPatch]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`CatalogUpdate`](../models/catalogupdate.md) |
| Response schema | [`CatalogEntry`](../models/catalogentry.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CatalogController.catalog_archive -->
<a id="catalogcontroller-catalog-archive"></a>
## Catalog archive

```http
POST /api/v1/tenants/{tenant_id}/catalog/{entry_id}/archive
```

Contract operation: `CatalogController.catalog_archive`.

| SDK | Method |
| --- | --- |
| Python | `archive` |
| TypeScript | `catalog.archive` |
| Java | `client.catalog.archive` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `entry_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`CatalogEntry`](../models/catalogentry.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CatalogController.catalog_restore -->
<a id="catalogcontroller-catalog-restore"></a>
## Catalog restore

```http
POST /api/v1/tenants/{tenant_id}/catalog/{entry_id}/restore
```

Contract operation: `CatalogController.catalog_restore`.

| SDK | Method |
| --- | --- |
| Python | `restore` |
| TypeScript | `catalog.restore` |
| Java | `client.catalog.restore` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `entry_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`CatalogEntry`](../models/catalogentry.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CatalogController.catalog_delete -->
<a id="catalogcontroller-catalog-delete"></a>
## Catalog delete

```http
DELETE /api/v1/tenants/{tenant_id}/catalog/{entry_id}
```

Contract operation: `CatalogController.catalog_delete`.

| SDK | Method |
| --- | --- |
| Python | `delete` |
| TypeScript | `catalog.delete` |
| Java | `client.catalog.delete` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `entry_id` | path | `PathVar[str]` | Yes | Not specified |

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

<!-- operation: CatalogProposalController.get -->
<a id="catalogproposalcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/proposals/{proposal_id}
```

Contract operation: `CatalogProposalController.get`.

| SDK | Method |
| --- | --- |
| Python | `proposal` |
| TypeScript | `chat.proposals.get` |
| Java | `client.chatProposals.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |
| `proposal_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`CatalogProposal`](../models/catalogproposal.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CatalogProposalController.confirm -->
<a id="catalogproposalcontroller-confirm"></a>
## Confirm

```http
POST /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/proposals/{proposal_id}/confirm
```

Contract operation: `CatalogProposalController.confirm`.

| SDK | Method |
| --- | --- |
| Python | `confirm_proposal` |
| TypeScript | `chat.proposals.confirm` |
| Java | `client.chatProposals.confirm` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |
| `proposal_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ProposalConfirmation]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ProposalConfirmation`](../models/proposalconfirmation.md) |
| Response schema | [`CatalogProposal`](../models/catalogproposal.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CatalogProposalController.cancel -->
<a id="catalogproposalcontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/proposals/{proposal_id}/cancel
```

Contract operation: `CatalogProposalController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_proposal` |
| TypeScript | `chat.proposals.cancel` |
| Java | `client.chatProposals.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |
| `proposal_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ProposalRevision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ProposalRevision`](../models/proposalrevision.md) |
| Response schema | [`CatalogProposal`](../models/catalogproposal.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
