<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Knowledge connections and indexes

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Roles](#knowledgeconnectionscontroller-roles) (GET)
- [List connections](#knowledgeconnectionscontroller-list-connections) (GET)
- [Create](#knowledgeconnectionscontroller-create) (POST)
- [Update](#knowledgeconnectionscontroller-update) (PUT)
- [Get](#knowledgeconnectionscontroller-get) (GET)
- [Delete](#knowledgeconnectionscontroller-delete) (DELETE)
- [List indexes](#knowledgeindexescontroller-list-indexes) (GET)
- [Choices](#knowledgeindexescontroller-choices) (GET)
- [Choice](#knowledgeindexescontroller-choice) (GET)
- [Get](#knowledgeindexescontroller-get) (GET)
- [Plan](#knowledgeindexescontroller-plan) (POST)
- [Create](#knowledgeindexescontroller-create) (POST)
- [Activate](#knowledgeindexescontroller-activate) (POST)
- [Cancel](#knowledgeindexescontroller-cancel) (POST)
- [Resume](#knowledgeindexescontroller-resume) (POST)
- [Get](#organizationknowledgecontroller-get) (GET)
- [Update](#organizationknowledgecontroller-update) (PUT)

<!-- operation: KnowledgeConnectionsController.roles -->
<a id="knowledgeconnectionscontroller-roles"></a>
## Roles

```http
GET /api/v1/tenants/{tenant_id}/knowledge-roles
```

Contract operation: `KnowledgeConnectionsController.roles`.

| SDK | Method |
| --- | --- |
| Python | `knowledge_roles` |
| TypeScript | `knowledgeConnections.roles` |
| Java | `client.knowledgeConnections.roles` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`KnowledgeRoles`](../models/knowledgeroles.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeConnectionsController.list_connections -->
<a id="knowledgeconnectionscontroller-list-connections"></a>
## List connections

```http
GET /api/v1/tenants/{tenant_id}/knowledge-connections
```

Contract operation: `KnowledgeConnectionsController.list_connections`.

| SDK | Method |
| --- | --- |
| Python | `knowledge_connections` |
| TypeScript | `knowledgeConnections.list` |
| Java | `client.knowledgeConnections.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[KnowledgeConnection]`](../models/page-knowledgeconnection.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeConnectionsController.create -->
<a id="knowledgeconnectionscontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/knowledge-connections
```

Contract operation: `KnowledgeConnectionsController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_knowledge_connection` |
| TypeScript | `knowledgeConnections.create` |
| Java | `client.knowledgeConnections.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ConnectionInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`KnowledgeConnectionInput`](../models/knowledgeconnectioninput.md) |
| Response schema | [`KnowledgeConnection`](../models/knowledgeconnection.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeConnectionsController.update -->
<a id="knowledgeconnectionscontroller-update"></a>
## Update

```http
PUT /api/v1/tenants/{tenant_id}/knowledge-connections/{connection_id}
```

Contract operation: `KnowledgeConnectionsController.update`.

| SDK | Method |
| --- | --- |
| Python | `update_knowledge_connection` |
| TypeScript | `knowledgeConnections.update` |
| Java | `client.knowledgeConnections.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `connection_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ConnectionInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`KnowledgeConnectionInput`](../models/knowledgeconnectioninput.md) |
| Response schema | [`KnowledgeConnection`](../models/knowledgeconnection.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeConnectionsController.get -->
<a id="knowledgeconnectionscontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/knowledge-connections/{connection_id}
```

Contract operation: `KnowledgeConnectionsController.get`.

| SDK | Method |
| --- | --- |
| Python | `knowledge_connection` |
| TypeScript | `knowledgeConnections.get` |
| Java | `client.knowledgeConnections.get` |

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
| Response schema | [`KnowledgeConnection`](../models/knowledgeconnection.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeConnectionsController.delete -->
<a id="knowledgeconnectionscontroller-delete"></a>
## Delete

```http
DELETE /api/v1/tenants/{tenant_id}/knowledge-connections/{connection_id}
```

Contract operation: `KnowledgeConnectionsController.delete`.

| SDK | Method |
| --- | --- |
| Python | `delete_knowledge_connection` |
| TypeScript | `knowledgeConnections.remove` |
| Java | `client.knowledgeConnections.remove` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `connection_id` | path | `PathVar[str]` | Yes | Not specified |
| `expected_revision` | query | `QueryParam[int]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Deleted`](../models/deleted.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeIndexesController.list_indexes -->
<a id="knowledgeindexescontroller-list-indexes"></a>
## List indexes

```http
GET /api/v1/tenants/{tenant_id}/knowledge-indexes
```

Contract operation: `KnowledgeIndexesController.list_indexes`.

| SDK | Method |
| --- | --- |
| Python | `knowledge_indexes` |
| TypeScript | `knowledgeIndexes.list` |
| Java | `client.knowledgeIndexes.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | `QueryParam[str]` | Yes | Not specified |
| `domain` | query | `QueryParam[str]` | Yes | Not specified |
| `limit` | query | `QueryParam[int]` | No | `50` |
| `offset` | query | `QueryParam[int]` | No | `0` |
| `status` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `dimensions` | query | <code>QueryParam&#91;int &#124; None&#93;</code> | No | `null` |
| `model_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `provider_kind` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`IndexPage`](../models/indexpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeIndexesController.choices -->
<a id="knowledgeindexescontroller-choices"></a>
## Choices

```http
GET /api/v1/tenants/{tenant_id}/knowledge-index-choices
```

Contract operation: `KnowledgeIndexesController.choices`.

| SDK | Method |
| --- | --- |
| Python | `native_index_choices` |
| TypeScript | `knowledgeIndexes.choices` |
| Java | `client.knowledgeIndexes.choices` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | `QueryParam[str]` | Yes | Not specified |
| `domain` | query | `QueryParam[str]` | Yes | Not specified |
| `limit` | query | `QueryParam[int]` | No | `50` |
| `offset` | query | `QueryParam[int]` | No | `0` |
| `status` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `dimensions` | query | <code>QueryParam&#91;int &#124; None&#93;</code> | No | `null` |
| `model_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `provider_kind` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`NativeIndexPage`](../models/nativeindexpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeIndexesController.choice -->
<a id="knowledgeindexescontroller-choice"></a>
## Choice

```http
GET /api/v1/tenants/{tenant_id}/knowledge-index-choices/{choice_id}
```

Contract operation: `KnowledgeIndexesController.choice`.

| SDK | Method |
| --- | --- |
| Python | `native_index_choice` |
| TypeScript | `knowledgeIndexes.choice` |
| Java | `client.knowledgeIndexes.choice` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `choice_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | `QueryParam[str]` | Yes | Not specified |
| `domain` | query | `QueryParam[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`NativeIndexChoice`](../models/nativeindexchoice.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeIndexesController.get -->
<a id="knowledgeindexescontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/knowledge-indexes/{index_id}
```

Contract operation: `KnowledgeIndexesController.get`.

| SDK | Method |
| --- | --- |
| Python | `knowledge_index` |
| TypeScript | `knowledgeIndexes.get` |
| Java | `client.knowledgeIndexes.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `index_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`KnowledgeIndexView`](../models/knowledgeindexview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeIndexesController.plan -->
<a id="knowledgeindexescontroller-plan"></a>
## Plan

```http
POST /api/v1/tenants/{tenant_id}/knowledge-indexes/plan
```

Contract operation: `KnowledgeIndexesController.plan`.

| SDK | Method |
| --- | --- |
| Python | `plan_knowledge_index` |
| TypeScript | `knowledgeIndexes.plan` |
| Java | `client.knowledgeIndexes.plan` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IndexPlanInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IndexPlanInput`](../models/indexplaninput.md) |
| Response schema | [`IndexPlanView`](../models/indexplanview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeIndexesController.create -->
<a id="knowledgeindexescontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/knowledge-indexes
```

Contract operation: `KnowledgeIndexesController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_knowledge_index` |
| TypeScript | `knowledgeIndexes.create` |
| Java | `client.knowledgeIndexes.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IndexCreateInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IndexCreateInput`](../models/indexcreateinput.md) |
| Response schema | [`IndexJobView`](../models/indexjobview.md) |
| Success status | `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeIndexesController.activate -->
<a id="knowledgeindexescontroller-activate"></a>
## Activate

```http
POST /api/v1/tenants/{tenant_id}/knowledge-indexes/{index_id}/activate
```

Contract operation: `KnowledgeIndexesController.activate`.

| SDK | Method |
| --- | --- |
| Python | `activate_knowledge_index` |
| TypeScript | `knowledgeIndexes.activate` |
| Java | `client.knowledgeIndexes.activate` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `index_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IndexActivateInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IndexActivateInput`](../models/indexactivateinput.md) |
| Response schema | [`KnowledgeIndexView`](../models/knowledgeindexview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeIndexesController.cancel -->
<a id="knowledgeindexescontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/knowledge-indexes/{index_id}/cancel
```

Contract operation: `KnowledgeIndexesController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_knowledge_index` |
| TypeScript | `knowledgeIndexes.cancel` |
| Java | `client.knowledgeIndexes.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `index_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IndexRevisionInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IndexRevisionInput`](../models/indexrevisioninput.md) |
| Response schema | [`KnowledgeIndexView`](../models/knowledgeindexview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: KnowledgeIndexesController.resume -->
<a id="knowledgeindexescontroller-resume"></a>
## Resume

```http
POST /api/v1/tenants/{tenant_id}/knowledge-indexes/{index_id}/resume
```

Contract operation: `KnowledgeIndexesController.resume`.

| SDK | Method |
| --- | --- |
| Python | `resume_knowledge_index` |
| TypeScript | `knowledgeIndexes.resume` |
| Java | `client.knowledgeIndexes.resume` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `index_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IndexRevisionInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IndexRevisionInput`](../models/indexrevisioninput.md) |
| Response schema | [`IndexJobView`](../models/indexjobview.md) |
| Success status | `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationKnowledgeController.get -->
<a id="organizationknowledgecontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/knowledge/settings
```

Contract operation: `OrganizationKnowledgeController.get`.

| SDK | Method |
| --- | --- |
| Python | `organization_knowledge_settings` |
| TypeScript | `organizationKnowledge.get` |
| Java | `client.organizationKnowledge.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OrganizationKnowledgeSettings`](../models/organizationknowledgesettings.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationKnowledgeController.update -->
<a id="organizationknowledgecontroller-update"></a>
## Update

```http
PUT /api/v1/tenants/{tenant_id}/knowledge/settings
```

Contract operation: `OrganizationKnowledgeController.update`.

| SDK | Method |
| --- | --- |
| Python | `update_organization_knowledge_settings` |
| TypeScript | `organizationKnowledge.update` |
| Java | `client.organizationKnowledge.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[OrganizationKnowledgeSettingsInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`OrganizationKnowledgeSettingsInput`](../models/organizationknowledgesettingsinput.md) |
| Response schema | [`OrganizationKnowledgeSettings`](../models/organizationknowledgesettings.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
