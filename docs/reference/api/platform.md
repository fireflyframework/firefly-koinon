<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Platform configuration and operations

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Audit](#auditcontroller-audit) (GET)
- [Context](#contextcontroller-context) (GET)
- [List](#jobcontroller-list) (GET)
- [Get](#jobcontroller-get) (GET)
- [Cancel](#jobcontroller-cancel) (POST)
- [Conversation](#evidencecontroller-conversation) (POST)
- [Defaults](#brandingdefaultscontroller-defaults) (GET)
- [Get](#organizationbrandingcontroller-get) (GET)
- [Update](#organizationbrandingcontroller-update) (PUT)
- [Reset](#organizationbrandingcontroller-reset) (POST)
- [Capabilities](#capabilitiescontroller-capabilities) (GET)

<!-- operation: AuditController.audit -->
<a id="auditcontroller-audit"></a>
## Audit

```http
GET /api/v1/tenants/{tenant_id}/audit
```

Contract operation: `AuditController.audit`.

| SDK | Method |
| --- | --- |
| Python | `audit` |
| TypeScript | `audit.list` |
| Java | `client.audit.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `action` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `subject` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `from_date` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `through_date` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `time_zone` | query | `QueryParam[str]` | No | `"UTC"` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |
| `sort` | query | `QueryParam[str]` | No | `"created_at"` |
| `order` | query | `QueryParam[str]` | No | `"desc"` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[AuditEvent]`](../models/page-auditevent.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ContextController.context -->
<a id="contextcontroller-context"></a>
## Context

```http
GET /api/v1/context
```

Contract operation: `ContextController.context`.

| SDK | Method |
| --- | --- |
| Python | `context` |
| TypeScript | `context` |
| Java | `client.platform.context` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ContextResponse`](../models/contextresponse.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: JobController.list -->
<a id="jobcontroller-list"></a>
## List

```http
GET /api/v1/tenants/{tenant_id}/jobs
```

Contract operation: `JobController.list`.

| SDK | Method |
| --- | --- |
| Python | `jobs` |
| TypeScript | `jobs.list` |
| Java | `client.jobs.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[Job]`](../models/page-job.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: JobController.get -->
<a id="jobcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/jobs/{job_id}
```

Contract operation: `JobController.get`.

| SDK | Method |
| --- | --- |
| Python | `job` |
| TypeScript | `jobs.get` |
| Java | `client.jobs.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `job_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Job`](../models/job.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: JobController.cancel -->
<a id="jobcontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/jobs/{job_id}/cancel
```

Contract operation: `JobController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_job` |
| TypeScript | `jobs.cancel` |
| Java | `client.jobs.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `job_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Job`](../models/job.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: EvidenceController.conversation -->
<a id="evidencecontroller-conversation"></a>
## Conversation

```http
POST /api/v1/tenants/{tenant_id}/evidence/conversations
```

Contract operation: `EvidenceController.conversation`.

| SDK | Method |
| --- | --- |
| Python | `conversation_evidence` |
| TypeScript | `evidence.conversation` |
| Java | `client.evidence.conversation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[MessageSelection]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`MessageSelection`](../models/messageselection.md) |
| Response schema | [`EvidenceManifest`](../models/evidencemanifest.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: BrandingDefaultsController.defaults -->
<a id="brandingdefaultscontroller-defaults"></a>
## Defaults

```http
GET /api/v1/branding/defaults
```

Contract operation: `BrandingDefaultsController.defaults`.

| SDK | Method |
| --- | --- |
| Python | `branding_defaults` |
| TypeScript | `branding.defaults` |
| Java | `client.brandingDefaults.defaults` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`BrandingValues`](../models/brandingvalues.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationBrandingController.get -->
<a id="organizationbrandingcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/branding
```

Contract operation: `OrganizationBrandingController.get`.

| SDK | Method |
| --- | --- |
| Python | `organization_branding` |
| TypeScript | `branding.get` |
| Java | `client.organizationBranding.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OrganizationBranding`](../models/organizationbranding.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationBrandingController.update -->
<a id="organizationbrandingcontroller-update"></a>
## Update

```http
PUT /api/v1/tenants/{tenant_id}/branding
```

Contract operation: `OrganizationBrandingController.update`.

| SDK | Method |
| --- | --- |
| Python | `update_organization_branding` |
| TypeScript | `branding.update` |
| Java | `client.organizationBranding.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[OrganizationBrandingInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`OrganizationBrandingInput`](../models/organizationbrandinginput.md) |
| Response schema | [`OrganizationBranding`](../models/organizationbranding.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationBrandingController.reset -->
<a id="organizationbrandingcontroller-reset"></a>
## Reset

```http
POST /api/v1/tenants/{tenant_id}/branding/reset
```

Contract operation: `OrganizationBrandingController.reset`.

| SDK | Method |
| --- | --- |
| Python | `reset_organization_branding` |
| TypeScript | `branding.reset` |
| Java | `client.organizationBranding.reset` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[BrandingResetInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`BrandingResetInput`](../models/brandingresetinput.md) |
| Response schema | [`OrganizationBranding`](../models/organizationbranding.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CapabilitiesController.capabilities -->
<a id="capabilitiescontroller-capabilities"></a>
## Capabilities

```http
GET /api/v1/capabilities
```

Contract operation: `CapabilitiesController.capabilities`.

| SDK | Method |
| --- | --- |
| Python | `capabilities` |
| TypeScript | `capabilities` |
| Java | `client.platform.capabilities` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Capabilities`](../models/capabilities.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
