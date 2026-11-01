<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Platform configuration and operations

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Personal](#activitycontroller-personal) (POST)
- [Administrative](#activitycontroller-administrative) (POST)
- [Audit](#auditcontroller-audit) (GET)
- [Context](#contextcontroller-context) (GET)
- [List](#jobcontroller-list) (GET)
- [Get](#jobcontroller-get) (GET)
- [Cancel](#jobcontroller-cancel) (POST)
- [Providers](#communicationscontroller-providers) (GET)
- [Recipients search](#communicationscontroller-recipients-search) (GET)
- [Preview](#communicationscontroller-preview) (POST)
- [Create](#communicationscontroller-create) (POST)
- [Page](#communicationscontroller-page) (GET)
- [Revoke](#communicationscontroller-revoke) (DELETE)
- [Resend](#communicationscontroller-resend) (POST)
- [Inspect](#communicationscontroller-inspect) (GET)
- [Accept](#communicationscontroller-accept) (POST)
- [Decline](#communicationscontroller-decline) (POST)
- [Capabilities](#communicationscontroller-capabilities) (GET)
- [Policy](#communicationscontroller-policy) (GET)
- [Policy update](#communicationscontroller-policy-update) (PATCH)
- [Deliveries](#communicationscontroller-deliveries) (GET)
- [Delivery](#communicationscontroller-delivery) (GET)
- [Retry](#communicationscontroller-retry) (POST)
- [Page](#notificationcontroller-page) (GET)
- [Unread count](#notificationcontroller-unread-count) (GET)
- [Read](#notificationcontroller-read) (POST)
- [Preferences](#notificationcontroller-preferences) (GET)
- [Preferences update](#notificationcontroller-preferences-update) (PATCH)
- [Preferences preview](#notificationcontroller-preferences-preview) (POST)
- [Email preview](#notificationcontroller-email-preview) (POST)
- [Conversation](#evidencecontroller-conversation) (POST)
- [Defaults](#brandingdefaultscontroller-defaults) (GET)
- [Get](#organizationbrandingcontroller-get) (GET)
- [Update](#organizationbrandingcontroller-update) (PUT)
- [Reset](#organizationbrandingcontroller-reset) (POST)
- [Health](#platformcontroller-health) (GET)
- [System information](#platformcontroller-system-information) (GET)
- [Capabilities](#capabilitiescontroller-capabilities) (GET)

<!-- operation: ActivityController.personal -->
<a id="activitycontroller-personal"></a>
## Personal

```http
POST /api/v1/tenants/{tenant_id}/activity/personal
```

Contract operation: `ActivityController.personal`.

| SDK | Method |
| --- | --- |
| Python | `personal_activity` |
| TypeScript | `activity.personal` |
| Java | `client.activity.personal` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ActivityWindow]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ActivityWindow`](../models/activitywindow.md) |
| Response schema | [`ActivitySummary`](../models/activitysummary.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ActivityController.administrative -->
<a id="activitycontroller-administrative"></a>
## Administrative

```http
POST /api/v1/tenants/{tenant_id}/activity/administration
```

Contract operation: `ActivityController.administrative`.

| SDK | Method |
| --- | --- |
| Python | `administrative_activity` |
| TypeScript | `activity.administrative` |
| Java | `client.activity.administrative` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ActivityWindow]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ActivityWindow`](../models/activitywindow.md) |
| Response schema | [`ActivitySummary`](../models/activitysummary.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

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

<!-- operation: CommunicationsController.providers -->
<a id="communicationscontroller-providers"></a>
## Providers

```http
GET /api/v1/tenants/{tenant_id}/communications/recipient-providers
```

Contract operation: `CommunicationsController.providers`.

| SDK | Method |
| --- | --- |
| Python | `communication_providers` |
| TypeScript | `communications.recipients.providers` |
| Java | `client.communications.recipientProviders` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `20` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`RecipientProviderPage`](../models/recipientproviderpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.recipients_search -->
<a id="communicationscontroller-recipients-search"></a>
## Recipients search

```http
GET /api/v1/tenants/{tenant_id}/communications/recipients
```

Contract operation: `CommunicationsController.recipients_search`.

| SDK | Method |
| --- | --- |
| Python | `communication_recipients` |
| TypeScript | `communications.recipients.list` |
| Java | `client.communications.recipients` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `provider_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `after` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `limit` | query | `QueryParam[int]` | No | `20` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DirectoryRecipientPage`](../models/directoryrecipientpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.preview -->
<a id="communicationscontroller-preview"></a>
## Preview

```http
POST /api/v1/tenants/{tenant_id}/invitations/email/preview
```

Contract operation: `CommunicationsController.preview`.

| SDK | Method |
| --- | --- |
| Python | `preview_email_invitation` |
| TypeScript | `communications.emailInvitations.preview` |
| Java | `client.communications.previewInvitation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[EmailInvitationInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`EmailInvitationInput`](../models/emailinvitationinput.md) |
| Response schema | [`EmailPreview`](../models/emailpreview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.create -->
<a id="communicationscontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/invitations/email
```

Contract operation: `CommunicationsController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_email_invitation` |
| TypeScript | `communications.emailInvitations.create` |
| Java | `client.communications.createInvitation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[EmailInvitationInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`EmailInvitationInput`](../models/emailinvitationinput.md) |
| Response schema | [`EmailInvitation`](../models/emailinvitation.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.page -->
<a id="communicationscontroller-page"></a>
## Page

```http
GET /api/v1/tenants/{tenant_id}/invitations/email
```

Contract operation: `CommunicationsController.page`.

| SDK | Method |
| --- | --- |
| Python | `email_invitations` |
| TypeScript | `communications.emailInvitations.list` |
| Java | `client.communications.invitations` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `status` | query | `QueryParam[str]` | No | `"pending"` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`EmailInvitationPage`](../models/emailinvitationpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.revoke -->
<a id="communicationscontroller-revoke"></a>
## Revoke

```http
DELETE /api/v1/tenants/{tenant_id}/invitations/email/{invitation_id}
```

Contract operation: `CommunicationsController.revoke`.

| SDK | Method |
| --- | --- |
| Python | `revoke_email_invitation` |
| TypeScript | `communications.emailInvitations.revoke` |
| Java | `client.communications.revokeInvitation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `invitation_id` | path | `PathVar[str]` | Yes | Not specified |

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

<!-- operation: CommunicationsController.resend -->
<a id="communicationscontroller-resend"></a>
## Resend

```http
POST /api/v1/tenants/{tenant_id}/invitations/email/{invitation_id}/resend
```

Contract operation: `CommunicationsController.resend`.

| SDK | Method |
| --- | --- |
| Python | `resend_email_invitation` |
| TypeScript | `communications.emailInvitations.resend` |
| Java | `client.communications.resendInvitation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `invitation_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`EmailInvitation`](../models/emailinvitation.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.inspect -->
<a id="communicationscontroller-inspect"></a>
## Inspect

```http
GET /api/v1/invitations/email/{invitation_id}
```

Contract operation: `CommunicationsController.inspect`.

| SDK | Method |
| --- | --- |
| Python | `email_invitation` |
| TypeScript | `communications.emailInvitations.review` |
| Java | `client.emailInvitations.review` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `invitation_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`InvitationReview`](../models/invitationreview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.accept -->
<a id="communicationscontroller-accept"></a>
## Accept

```http
POST /api/v1/invitations/email/{invitation_id}/accept
```

Contract operation: `CommunicationsController.accept`.

| SDK | Method |
| --- | --- |
| Python | `accept_email_invitation` |
| TypeScript | `communications.emailInvitations.accept` |
| Java | `client.emailInvitations.accept` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `invitation_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Membership`](../models/membership.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.decline -->
<a id="communicationscontroller-decline"></a>
## Decline

```http
POST /api/v1/invitations/email/{invitation_id}/decline
```

Contract operation: `CommunicationsController.decline`.

| SDK | Method |
| --- | --- |
| Python | `decline_email_invitation` |
| TypeScript | `communications.emailInvitations.decline` |
| Java | `client.emailInvitations.decline` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `invitation_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`InvitationReview`](../models/invitationreview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.capabilities -->
<a id="communicationscontroller-capabilities"></a>
## Capabilities

```http
GET /api/v1/tenants/{tenant_id}/communications/capabilities
```

Contract operation: `CommunicationsController.capabilities`.

| SDK | Method |
| --- | --- |
| Python | `communications_capabilities` |
| TypeScript | `communications.administration.capabilities` |
| Java | `client.communications.capabilities` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`CommunicationCapabilities`](../models/communicationcapabilities.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.policy -->
<a id="communicationscontroller-policy"></a>
## Policy

```http
GET /api/v1/tenants/{tenant_id}/communications/policy
```

Contract operation: `CommunicationsController.policy`.

| SDK | Method |
| --- | --- |
| Python | `communications_policy` |
| TypeScript | `communications.administration.policy` |
| Java | `client.communications.policy` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`CommunicationPolicy`](../models/communicationpolicy.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.policy_update -->
<a id="communicationscontroller-policy-update"></a>
## Policy update

```http
PATCH /api/v1/tenants/{tenant_id}/communications/policy
```

Contract operation: `CommunicationsController.policy_update`.

| SDK | Method |
| --- | --- |
| Python | `update_communications_policy` |
| TypeScript | `communications.administration.updatePolicy` |
| Java | `client.communications.updatePolicy` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[CommunicationPolicyInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`CommunicationPolicyInput`](../models/communicationpolicyinput.md) |
| Response schema | [`CommunicationPolicy`](../models/communicationpolicy.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.deliveries -->
<a id="communicationscontroller-deliveries"></a>
## Deliveries

```http
GET /api/v1/tenants/{tenant_id}/communications/deliveries
```

Contract operation: `CommunicationsController.deliveries`.

| SDK | Method |
| --- | --- |
| Python | `communication_deliveries` |
| TypeScript | `communications.administration.deliveries` |
| Java | `client.communications.deliveries` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `status` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `kind` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `channel` | query | `QueryParam[str]` | No | `"email"` |
| `created_from` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `created_to` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DeliveryPage`](../models/deliverypage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.delivery -->
<a id="communicationscontroller-delivery"></a>
## Delivery

```http
GET /api/v1/tenants/{tenant_id}/communications/deliveries/{delivery_id}
```

Contract operation: `CommunicationsController.delivery`.

| SDK | Method |
| --- | --- |
| Python | `communication_delivery` |
| TypeScript | `communications.administration.delivery` |
| Java | `client.communications.delivery` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `delivery_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DeliveryRecord`](../models/deliveryrecord.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CommunicationsController.retry -->
<a id="communicationscontroller-retry"></a>
## Retry

```http
POST /api/v1/tenants/{tenant_id}/communications/deliveries/{delivery_id}/retry
```

Contract operation: `CommunicationsController.retry`.

| SDK | Method |
| --- | --- |
| Python | `retry_communication_delivery` |
| TypeScript | `communications.administration.retry` |
| Java | `client.communications.retryDelivery` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `delivery_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`DeliveryRecord`](../models/deliveryrecord.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: NotificationController.page -->
<a id="notificationcontroller-page"></a>
## Page

```http
GET /api/v1/notifications
```

Contract operation: `NotificationController.page`.

| SDK | Method |
| --- | --- |
| Python | `notifications` |
| TypeScript | `communications.notifications.list` |
| Java | `client.notifications.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `kind` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `read` | query | `QueryParam[str]` | No | `"all"` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OwnNotificationPage`](../models/ownnotificationpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: NotificationController.unread_count -->
<a id="notificationcontroller-unread-count"></a>
## Unread count

```http
GET /api/v1/notifications/unread-count
```

Contract operation: `NotificationController.unread_count`.

| SDK | Method |
| --- | --- |
| Python | `notification_unread_count` |
| TypeScript | `communications.notifications.unreadCount` |
| Java | `client.notifications.unreadCount` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`NotificationUnreadCount`](../models/notificationunreadcount.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: NotificationController.read -->
<a id="notificationcontroller-read"></a>
## Read

```http
POST /api/v1/notifications/{notification_id}/read
```

Contract operation: `NotificationController.read`.

| SDK | Method |
| --- | --- |
| Python | `read_notification` |
| TypeScript | `communications.notifications.markRead` |
| Java | `client.notifications.markRead` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `notification_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OwnNotification`](../models/ownnotification.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: NotificationController.preferences -->
<a id="notificationcontroller-preferences"></a>
## Preferences

```http
GET /api/v1/notifications/preferences
```

Contract operation: `NotificationController.preferences`.

| SDK | Method |
| --- | --- |
| Python | `notification_preferences` |
| TypeScript | `communications.notifications.preferences` |
| Java | `client.notifications.preferences` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`NotificationPreferences`](../models/notificationpreferences.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: NotificationController.preferences_update -->
<a id="notificationcontroller-preferences-update"></a>
## Preferences update

```http
PATCH /api/v1/notifications/preferences
```

Contract operation: `NotificationController.preferences_update`.

| SDK | Method |
| --- | --- |
| Python | `update_notification_preferences` |
| TypeScript | `communications.notifications.updatePreferences` |
| Java | `client.notifications.updatePreferences` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `body` | body | `Valid[Body[NotificationPreferencesInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`NotificationPreferencesInput`](../models/notificationpreferencesinput.md) |
| Response schema | [`NotificationPreferences`](../models/notificationpreferences.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: NotificationController.preferences_preview -->
<a id="notificationcontroller-preferences-preview"></a>
## Preferences preview

```http
POST /api/v1/notifications/preferences/preview
```

Contract operation: `NotificationController.preferences_preview`.

| SDK | Method |
| --- | --- |
| Python | `preview_notification_schedule` |
| TypeScript | `communications.notifications.previewPreferences` |
| Java | `client.notifications.previewSchedule` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `body` | body | `Valid[Body[NotificationPreferencesInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`NotificationPreferencesInput`](../models/notificationpreferencesinput.md) |
| Response schema | [`DigestSchedulePreview`](../models/digestschedulepreview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: NotificationController.email_preview -->
<a id="notificationcontroller-email-preview"></a>
## Email preview

```http
POST /api/v1/notifications/preferences/email-preview
```

Contract operation: `NotificationController.email_preview`.

| SDK | Method |
| --- | --- |
| Python | `preview_activity_email` |
| TypeScript | `communications.notifications.previewEmail` |
| Java | `client.notifications.previewEmail` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `body` | body | `Valid[Body[ActivityEmailPreviewInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ActivityEmailPreviewInput`](../models/activityemailpreviewinput.md) |
| Response schema | [`EmailPreview`](../models/emailpreview.md) |
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

<!-- operation: PlatformController.health -->
<a id="platformcontroller-health"></a>
## Health

```http
GET /api/v1/tenants/{tenant_id}/platform/health
```

Contract operation: `PlatformController.health`.

| SDK | Method |
| --- | --- |
| Python | `platform_health` |
| TypeScript | `platformHealth.health` |
| Java | `client.platformHealth.health` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`PlatformHealth`](../models/platformhealth.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: PlatformController.system_information -->
<a id="platformcontroller-system-information"></a>
## System information

```http
GET /api/v1/tenants/{tenant_id}/platform/system-information
```

Contract operation: `PlatformController.system_information`.

| SDK | Method |
| --- | --- |
| Python | `system_information` |
| TypeScript | `platformHealth.systemInformation` |
| Java | `client.platformHealth.systemInformation` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`SystemInformation`](../models/systeminformation.md) |
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
