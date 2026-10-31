<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Applications and MCP

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [List](#authorizedapplicationcontroller-list) (GET)
- [Detail](#authorizedapplicationcontroller-detail) (GET)
- [Revoke](#authorizedapplicationcontroller-revoke) (DELETE)
- [Stage](#externalknowledgereviewcontroller-stage) (POST)
- [Get](#externalknowledgereviewcontroller-get) (GET)
- [Approve](#externalknowledgereviewcontroller-approve) (POST)
- [Cancel](#externalknowledgereviewcontroller-cancel) (POST)
- [Cleanup](#externalfilereviewcontroller-cleanup) (POST)
- [Stage](#externalfilereviewcontroller-stage) (POST)
- [Get](#externalfilereviewcontroller-get) (GET)
- [Chunk](#externalfilereviewcontroller-chunk) (POST)
- [Seal](#externalfilereviewcontroller-seal) (POST)
- [Approve](#externalfilereviewcontroller-approve) (POST)
- [Cancel](#externalfilereviewcontroller-cancel) (POST)
- [Get](#mcpconnectioncontroller-get) (GET)
- [Get](#mcporganizationconnectioncontroller-get) (GET)
- [Readiness](#mcpoauthclientcontroller-readiness) (GET)
- [Page](#mcpoauthclientcontroller-page) (GET)
- [Create](#mcpoauthclientcontroller-create) (POST)
- [Retrieve](#mcpoauthclientcontroller-retrieve) (GET)
- [Update](#mcpoauthclientcontroller-update) (PATCH)
- [Rotate secret](#mcpoauthclientcontroller-rotate-secret) (POST)

<!-- operation: AuthorizedApplicationController.list -->
<a id="authorizedapplicationcontroller-list"></a>
## List

```http
GET /api/v1/authorized-applications
```

Contract operation: `AuthorizedApplicationController.list`.

| SDK | Method |
| --- | --- |
| Python | `authorized_applications` |
| TypeScript | `authorizedApplications.list` |
| Java | `client.authorizedApplications.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `q` | query | `QueryParam[str]` | No | `""` |
| `status` | query | `QueryParam[str]` | No | `"all"` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |
| `sort` | query | `QueryParam[str]` | No | `"connected_at"` |
| `order` | query | `QueryParam[str]` | No | `"desc"` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[AuthorizedApplication]`](../models/page-authorizedapplication.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AuthorizedApplicationController.detail -->
<a id="authorizedapplicationcontroller-detail"></a>
## Detail

```http
GET /api/v1/authorized-applications/{application_id}
```

Contract operation: `AuthorizedApplicationController.detail`.

| SDK | Method |
| --- | --- |
| Python | `authorized_application` |
| TypeScript | `authorizedApplications.get` |
| Java | `client.authorizedApplications.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `application_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`AuthorizedApplication`](../models/authorizedapplication.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AuthorizedApplicationController.revoke -->
<a id="authorizedapplicationcontroller-revoke"></a>
## Revoke

```http
DELETE /api/v1/authorized-applications/{application_id}
```

Contract operation: `AuthorizedApplicationController.revoke`.

| SDK | Method |
| --- | --- |
| Python | `revoke_authorized_application` |
| TypeScript | `authorizedApplications.revoke` |
| Java | `client.authorizedApplications.revoke` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `application_id` | path | `PathVar[str]` | Yes | Not specified |

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

<!-- operation: ExternalKnowledgeReviewController.stage -->
<a id="externalknowledgereviewcontroller-stage"></a>
## Stage

```http
POST /api/v1/tenants/{tenant_id}/external-knowledge-reviews
```

Contract operation: `ExternalKnowledgeReviewController.stage`.

| SDK | Method |
| --- | --- |
| Python | `stage_external_review` |
| TypeScript | `externalReviews.stage` |
| Java | `client.externalReviews.stage` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExternalReviewInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExternalReviewInput`](../models/externalreviewinput.md) |
| Response schema | [`ExternalReviewView`](../models/externalreviewview.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalKnowledgeReviewController.get -->
<a id="externalknowledgereviewcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/external-knowledge-reviews/{review_id}
```

Contract operation: `ExternalKnowledgeReviewController.get`.

| SDK | Method |
| --- | --- |
| Python | `external_review` |
| TypeScript | `externalReviews.get` |
| Java | `client.externalReviews.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `review_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ExternalReviewView`](../models/externalreviewview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalKnowledgeReviewController.approve -->
<a id="externalknowledgereviewcontroller-approve"></a>
## Approve

```http
POST /api/v1/tenants/{tenant_id}/external-knowledge-reviews/{review_id}/approve
```

Contract operation: `ExternalKnowledgeReviewController.approve`.

| SDK | Method |
| --- | --- |
| Python | `approve_external_review` |
| TypeScript | `externalReviews.approve` |
| Java | `client.externalReviews.approve` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `review_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExternalReviewDecision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExternalReviewDecision`](../models/externalreviewdecision.md) |
| Response schema | [`KnowledgeCommitOutcome`](../models/knowledgecommitoutcome.md) |
| Success status | `200`, `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalKnowledgeReviewController.cancel -->
<a id="externalknowledgereviewcontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/external-knowledge-reviews/{review_id}/cancel
```

Contract operation: `ExternalKnowledgeReviewController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_external_review` |
| TypeScript | `externalReviews.cancel` |
| Java | `client.externalReviews.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `review_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExternalReviewDecision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExternalReviewDecision`](../models/externalreviewdecision.md) |
| Response schema | [`ExternalReviewView`](../models/externalreviewview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalFileReviewController.cleanup -->
<a id="externalfilereviewcontroller-cleanup"></a>
## Cleanup

```http
POST /api/v1/tenants/{tenant_id}/external-file-reviews/cleanup
```

Contract operation: `ExternalFileReviewController.cleanup`.

| SDK | Method |
| --- | --- |
| Python | `cleanup_external_file_reviews` |
| TypeScript | `externalFileReviews.cleanup` |
| Java | `client.externalFileReviews.cleanup` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExternalFileCleanupInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExternalFileCleanupInput`](../models/externalfilecleanupinput.md) |
| Response schema | [`ExternalFileCleanupResult`](../models/externalfilecleanupresult.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalFileReviewController.stage -->
<a id="externalfilereviewcontroller-stage"></a>
## Stage

```http
POST /api/v1/tenants/{tenant_id}/external-file-reviews
```

Contract operation: `ExternalFileReviewController.stage`.

| SDK | Method |
| --- | --- |
| Python | `stage_external_file_review` |
| TypeScript | `externalFileReviews.stage` |
| Java | `client.externalFileReviews.stage` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExternalFileReviewInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExternalFileReviewInput`](../models/externalfilereviewinput.md) |
| Response schema | [`ExternalFileReviewView`](../models/externalfilereviewview.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalFileReviewController.get -->
<a id="externalfilereviewcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}
```

Contract operation: `ExternalFileReviewController.get`.

| SDK | Method |
| --- | --- |
| Python | `external_file_review` |
| TypeScript | `externalFileReviews.get` |
| Java | `client.externalFileReviews.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `review_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ExternalFileReviewView`](../models/externalfilereviewview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalFileReviewController.chunk -->
<a id="externalfilereviewcontroller-chunk"></a>
## Chunk

```http
POST /api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}/chunks
```

Contract operation: `ExternalFileReviewController.chunk`.

| SDK | Method |
| --- | --- |
| Python | `upload_external_file_chunk` |
| TypeScript | `externalFileReviews.chunk` |
| Java | `client.externalFileReviews.chunk` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `review_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExternalFileChunkInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExternalFileChunkInput`](../models/externalfilechunkinput.md) |
| Response schema | [`ExternalFileReviewView`](../models/externalfilereviewview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalFileReviewController.seal -->
<a id="externalfilereviewcontroller-seal"></a>
## Seal

```http
POST /api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}/seal
```

Contract operation: `ExternalFileReviewController.seal`.

| SDK | Method |
| --- | --- |
| Python | `seal_external_file_review` |
| TypeScript | `externalFileReviews.seal` |
| Java | `client.externalFileReviews.seal` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `review_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ExternalFileReviewView`](../models/externalfilereviewview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalFileReviewController.approve -->
<a id="externalfilereviewcontroller-approve"></a>
## Approve

```http
POST /api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}/approve
```

Contract operation: `ExternalFileReviewController.approve`.

| SDK | Method |
| --- | --- |
| Python | `approve_external_file_review` |
| TypeScript | `externalFileReviews.approve` |
| Java | `client.externalFileReviews.approve` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `review_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExternalReviewDecision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExternalReviewDecision`](../models/externalreviewdecision.md) |
| Response schema | [`ExternalFileReviewView`](../models/externalfilereviewview.md) |
| Success status | `200`, `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ExternalFileReviewController.cancel -->
<a id="externalfilereviewcontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}/cancel
```

Contract operation: `ExternalFileReviewController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_external_file_review` |
| TypeScript | `externalFileReviews.cancel` |
| Java | `client.externalFileReviews.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `review_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ExternalReviewDecision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ExternalReviewDecision`](../models/externalreviewdecision.md) |
| Response schema | [`ExternalFileReviewView`](../models/externalfilereviewview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: McpConnectionController.get -->
<a id="mcpconnectioncontroller-get"></a>
## Get

```http
GET /api/v1/mcp/connection
```

Contract operation: `McpConnectionController.get`.

| SDK | Method |
| --- | --- |
| Python | `mcp_connection` |
| TypeScript | `mcp.connection` |
| Java | `client.mcp.connection` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`McpConnectionDescriptor`](../models/mcpconnectiondescriptor.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: McpOrganizationConnectionController.get -->
<a id="mcporganizationconnectioncontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/mcp/connection
```

Contract operation: `McpOrganizationConnectionController.get`.

| SDK | Method |
| --- | --- |
| Python | `organization_mcp_connection` |
| TypeScript | `mcp.organizationConnection` |
| Java | `client.mcp.organizationConnection` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`McpConnectionDescriptor`](../models/mcpconnectiondescriptor.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: McpOAuthClientController.readiness -->
<a id="mcpoauthclientcontroller-readiness"></a>
## Readiness

```http
GET /api/v1/tenants/{tenant_id}/mcp/oauth-clients/readiness
```

Contract operation: `McpOAuthClientController.readiness`.

| SDK | Method |
| --- | --- |
| Python | `mcp_oauth_clients_readiness` |
| TypeScript | `mcpOAuthClients.readiness` |
| Java | `client.mcpOAuthClients.readiness` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`McpOAuthClientReadiness`](../models/mcpoauthclientreadiness.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: McpOAuthClientController.page -->
<a id="mcpoauthclientcontroller-page"></a>
## Page

```http
GET /api/v1/tenants/{tenant_id}/mcp/oauth-clients
```

Contract operation: `McpOAuthClientController.page`.

| SDK | Method |
| --- | --- |
| Python | `mcp_oauth_clients` |
| TypeScript | `mcpOAuthClients.list` |
| Java | `client.mcpOAuthClients.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `status` | query | `QueryParam[str]` | No | `"all"` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |
| `sort` | query | `QueryParam[str]` | No | `"name"` |
| `order` | query | `QueryParam[str]` | No | `"asc"` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`McpOAuthClientPage`](../models/mcpoauthclientpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: McpOAuthClientController.create -->
<a id="mcpoauthclientcontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/mcp/oauth-clients
```

Contract operation: `McpOAuthClientController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_mcp_oauth_client` |
| TypeScript | `mcpOAuthClients.create` |
| Java | `client.mcpOAuthClients.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[McpOAuthClientInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`McpOAuthClientInput`](../models/mcpoauthclientinput.md) |
| Response schema | [`McpOAuthClientCredential`](../models/mcpoauthclientcredential.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: McpOAuthClientController.retrieve -->
<a id="mcpoauthclientcontroller-retrieve"></a>
## Retrieve

```http
GET /api/v1/tenants/{tenant_id}/mcp/oauth-clients/{client_id}
```

Contract operation: `McpOAuthClientController.retrieve`.

| SDK | Method |
| --- | --- |
| Python | `mcp_oauth_client` |
| TypeScript | `mcpOAuthClients.get` |
| Java | `client.mcpOAuthClients.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `client_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`McpOAuthClient`](../models/mcpoauthclient.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: McpOAuthClientController.update -->
<a id="mcpoauthclientcontroller-update"></a>
## Update

```http
PATCH /api/v1/tenants/{tenant_id}/mcp/oauth-clients/{client_id}
```

Contract operation: `McpOAuthClientController.update`.

| SDK | Method |
| --- | --- |
| Python | `update_mcp_oauth_client` |
| TypeScript | `mcpOAuthClients.update` |
| Java | `client.mcpOAuthClients.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `client_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[McpOAuthClientPatch]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`McpOAuthClientPatch`](../models/mcpoauthclientpatch.md) |
| Response schema | [`McpOAuthClient`](../models/mcpoauthclient.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: McpOAuthClientController.rotate_secret -->
<a id="mcpoauthclientcontroller-rotate-secret"></a>
## Rotate secret

```http
POST /api/v1/tenants/{tenant_id}/mcp/oauth-clients/{client_id}/rotate-secret
```

Contract operation: `McpOAuthClientController.rotate_secret`.

| SDK | Method |
| --- | --- |
| Python | `rotate_mcp_oauth_client_secret` |
| TypeScript | `mcpOAuthClients.rotateSecret` |
| Java | `client.mcpOAuthClients.rotateSecret` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `client_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[McpOAuthClientRevision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`McpOAuthClientRevision`](../models/mcpoauthclientrevision.md) |
| Response schema | [`McpOAuthClientCredential`](../models/mcpoauthclientcredential.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
