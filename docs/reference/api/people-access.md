<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# People and access

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Members](#membershipcontroller-members) (GET)
- [Member create](#membershipcontroller-member-create) (POST)
- [Member patch](#membershipcontroller-member-patch) (PATCH)
- [Member delete](#membershipcontroller-member-delete) (DELETE)
- [Invitations list](#membershipcontroller-invitations-list) (GET)
- [Invitation create](#membershipcontroller-invitation-create) (POST)
- [Invitation revoke](#membershipcontroller-invitation-revoke) (DELETE)
- [Invitation inspect](#membershipcontroller-invitation-inspect) (POST)
- [Invitation redeem](#membershipcontroller-invitation-redeem) (POST)
- [Self](#organizationpeoplecontroller-self) (GET)
- [Page](#organizationpeoplecontroller-page) (GET)
- [Create](#organizationpeoplecontroller-create) (POST)
- [Get](#organizationpeoplecontroller-get) (GET)
- [Update](#organizationpeoplecontroller-update) (PATCH)
- [Avatar](#organizationpeoplecontroller-avatar) (GET)
- [Reports](#organizationpeoplecontroller-reports) (GET)
- [Units](#organizationpeoplecontroller-units) (GET)
- [Create unit](#organizationpeoplecontroller-create-unit) (POST)
- [Update unit](#organizationpeoplecontroller-update-unit) (PATCH)
- [Delete unit](#organizationpeoplecontroller-delete-unit) (DELETE)
- [Settings](#organizationpeoplecontroller-settings) (GET)
- [Update settings](#organizationpeoplecontroller-update-settings) (PATCH)
- [Mapping](#organizationpeoplecontroller-mapping) (GET)
- [Update mapping](#organizationpeoplecontroller-update-mapping) (PUT)

<!-- operation: MembershipController.members -->
<a id="membershipcontroller-members"></a>
## Members

```http
GET /api/v1/tenants/{tenant_id}/members
```

Contract operation: `MembershipController.members`.

| SDK | Method |
| --- | --- |
| Python | `members` |
| TypeScript | `members.list` |
| Java | `client.members.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `q` | query | `QueryParam[str]` | No | `""` |
| `role` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `scope` | query | `QueryParam[str]` | No | `"all"` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[Membership]`](../models/page-membership.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: MembershipController.member_create -->
<a id="membershipcontroller-member-create"></a>
## Member create

```http
POST /api/v1/tenants/{tenant_id}/members
```

Contract operation: `MembershipController.member_create`.

| SDK | Method |
| --- | --- |
| Python | `add_member` |
| TypeScript | `members.add` |
| Java | `client.members.add` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[MemberCreate]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`MemberInput`](../models/memberinput.md) |
| Response schema | [`Membership`](../models/membership.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: MembershipController.member_patch -->
<a id="membershipcontroller-member-patch"></a>
## Member patch

```http
PATCH /api/v1/tenants/{tenant_id}/members/{member_id}
```

Contract operation: `MembershipController.member_patch`.

| SDK | Method |
| --- | --- |
| Python | `update_member` |
| TypeScript | `members.update` |
| Java | `client.members.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `member_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[MemberPatch]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`MemberUpdate`](../models/memberupdate.md) |
| Response schema | [`Membership`](../models/membership.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: MembershipController.member_delete -->
<a id="membershipcontroller-member-delete"></a>
## Member delete

```http
DELETE /api/v1/tenants/{tenant_id}/members/{member_id}
```

Contract operation: `MembershipController.member_delete`.

| SDK | Method |
| --- | --- |
| Python | `remove_member` |
| TypeScript | `members.remove` |
| Java | `client.members.remove` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `member_id` | path | `PathVar[str]` | Yes | Not specified |

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

<!-- operation: MembershipController.invitations_list -->
<a id="membershipcontroller-invitations-list"></a>
## Invitations list

```http
GET /api/v1/tenants/{tenant_id}/invitations
```

Contract operation: `MembershipController.invitations_list`.

| SDK | Method |
| --- | --- |
| Python | `invitations` |
| TypeScript | `invitations.list` |
| Java | `client.invitations.list` |

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
| Response schema | [`Page[Invitation]`](../models/page-invitation.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: MembershipController.invitation_create -->
<a id="membershipcontroller-invitation-create"></a>
## Invitation create

```http
POST /api/v1/tenants/{tenant_id}/invitations
```

Contract operation: `MembershipController.invitation_create`.

| SDK | Method |
| --- | --- |
| Python | `create_invitation` |
| TypeScript | `invitations.create` |
| Java | `client.invitations.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[InvitationInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`InvitationInput`](../models/invitationinput.md) |
| Response schema | [`InvitationCreated`](../models/invitationcreated.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: MembershipController.invitation_revoke -->
<a id="membershipcontroller-invitation-revoke"></a>
## Invitation revoke

```http
DELETE /api/v1/tenants/{tenant_id}/invitations/{invitation_id}
```

Contract operation: `MembershipController.invitation_revoke`.

| SDK | Method |
| --- | --- |
| Python | `revoke_invitation` |
| TypeScript | `invitations.revoke` |
| Java | `client.invitations.revoke` |

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

<!-- operation: MembershipController.invitation_inspect -->
<a id="membershipcontroller-invitation-inspect"></a>
## Invitation inspect

```http
POST /api/v1/invitations/inspect
```

Contract operation: `MembershipController.invitation_inspect`.

| SDK | Method |
| --- | --- |
| Python | `inspect_invitation` |
| TypeScript | `invitations.inspect` |
| Java | `client.invitationAccess.inspect` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `body` | body | `Valid[Body[InvitationToken]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`InvitationToken`](../models/invitationtoken.md) |
| Response schema | [`InvitationPreview`](../models/invitationpreview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: MembershipController.invitation_redeem -->
<a id="membershipcontroller-invitation-redeem"></a>
## Invitation redeem

```http
POST /api/v1/invitations/redeem
```

Contract operation: `MembershipController.invitation_redeem`.

| SDK | Method |
| --- | --- |
| Python | `redeem_invitation` |
| TypeScript | `invitations.redeem` |
| Java | `client.invitationAccess.redeem` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `body` | body | `Valid[Body[InvitationToken]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`InvitationToken`](../models/invitationtoken.md) |
| Response schema | [`Membership`](../models/membership.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.self -->
<a id="organizationpeoplecontroller-self"></a>
## Self

```http
GET /api/v1/tenants/{tenant_id}/organization/people/me
```

Contract operation: `OrganizationPeopleController.self`.

| SDK | Method |
| --- | --- |
| Python | `organization_person_self` |
| TypeScript | `organizationPeople.me` |
| Java | `client.organizationPeople.me` |

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
| Response schema | [`OrganizationPerson`](../models/organizationperson.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.page -->
<a id="organizationpeoplecontroller-page"></a>
## Page

```http
GET /api/v1/tenants/{tenant_id}/organization/people
```

Contract operation: `OrganizationPeopleController.page`.

| SDK | Method |
| --- | --- |
| Python | `organization_people` |
| TypeScript | `organizationPeople.list` |
| Java | `client.organizationPeople.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `q` | query | `QueryParam[str]` | No | `""` |
| `job_title` | query | `QueryParam[str]` | No | `""` |
| `unit_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `department_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `manager_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `unassigned` | query | `QueryParam[bool]` | No | `false` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OrganizationPersonPage`](../models/organizationpersonpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.create -->
<a id="organizationpeoplecontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/organization/people
```

Contract operation: `OrganizationPeopleController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_organization_person` |
| TypeScript | `organizationPeople.create` |
| Java | `client.organizationPeople.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[OrganizationPersonCreate]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`OrganizationPersonCreate`](../models/organizationpersoncreate.md) |
| Response schema | [`OrganizationPerson`](../models/organizationperson.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.get -->
<a id="organizationpeoplecontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/organization/people/{person_id}
```

Contract operation: `OrganizationPeopleController.get`.

| SDK | Method |
| --- | --- |
| Python | `organization_person` |
| TypeScript | `organizationPeople.get` |
| Java | `client.organizationPeople.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `person_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OrganizationPerson`](../models/organizationperson.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.update -->
<a id="organizationpeoplecontroller-update"></a>
## Update

```http
PATCH /api/v1/tenants/{tenant_id}/organization/people/{person_id}
```

Contract operation: `OrganizationPeopleController.update`.

| SDK | Method |
| --- | --- |
| Python | `update_organization_person` |
| TypeScript | `organizationPeople.update` |
| Java | `client.organizationPeople.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `person_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[OrganizationPersonPatch]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`OrganizationPersonPatch`](../models/organizationpersonpatch.md) |
| Response schema | [`OrganizationPerson`](../models/organizationperson.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.avatar -->
<a id="organizationpeoplecontroller-avatar"></a>
## Avatar

```http
GET /api/v1/tenants/{tenant_id}/organization/people/{person_id}/avatar
```

Contract operation: `OrganizationPeopleController.avatar`.

| SDK | Method |
| --- | --- |
| Python | `organization_person_avatar` |
| TypeScript | `organizationPeople.avatar` |
| Java | `client.organizationPeople.avatar` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `person_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`BinaryDownload`](../models/binarydownload.md) |
| Success status | `200` |
| Declared encoding | `binary` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `If-None-Match (optional; avatars only)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.reports -->
<a id="organizationpeoplecontroller-reports"></a>
## Reports

```http
GET /api/v1/tenants/{tenant_id}/organization/people/{person_id}/reports
```

Contract operation: `OrganizationPeopleController.reports`.

| SDK | Method |
| --- | --- |
| Python | `organization_person_reports` |
| TypeScript | `organizationPeople.reports` |
| Java | `client.organizationPeople.reports` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `person_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OrganizationPersonPage`](../models/organizationpersonpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.units -->
<a id="organizationpeoplecontroller-units"></a>
## Units

```http
GET /api/v1/tenants/{tenant_id}/organization/units
```

Contract operation: `OrganizationPeopleController.units`.

| SDK | Method |
| --- | --- |
| Python | `organization_units` |
| TypeScript | `organizationPeople.units` |
| Java | `client.organizationPeople.units` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `parent_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `q` | query | `QueryParam[str]` | No | `""` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OrganizationUnitPage`](../models/organizationunitpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.create_unit -->
<a id="organizationpeoplecontroller-create-unit"></a>
## Create unit

```http
POST /api/v1/tenants/{tenant_id}/organization/units
```

Contract operation: `OrganizationPeopleController.create_unit`.

| SDK | Method |
| --- | --- |
| Python | `create_organization_unit` |
| TypeScript | `organizationPeople.createUnit` |
| Java | `client.organizationPeople.createUnit` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[OrganizationUnitInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`OrganizationUnitInput`](../models/organizationunitinput.md) |
| Response schema | [`OrganizationUnit`](../models/organizationunit.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.update_unit -->
<a id="organizationpeoplecontroller-update-unit"></a>
## Update unit

```http
PATCH /api/v1/tenants/{tenant_id}/organization/units/{unit_id}
```

Contract operation: `OrganizationPeopleController.update_unit`.

| SDK | Method |
| --- | --- |
| Python | `update_organization_unit` |
| TypeScript | `organizationPeople.updateUnit` |
| Java | `client.organizationPeople.updateUnit` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `unit_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[OrganizationUnitPatch]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`OrganizationUnitPatch`](../models/organizationunitpatch.md) |
| Response schema | [`OrganizationUnit`](../models/organizationunit.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.delete_unit -->
<a id="organizationpeoplecontroller-delete-unit"></a>
## Delete unit

```http
DELETE /api/v1/tenants/{tenant_id}/organization/units/{unit_id}
```

Contract operation: `OrganizationPeopleController.delete_unit`.

| SDK | Method |
| --- | --- |
| Python | `delete_organization_unit` |
| TypeScript | `organizationPeople.deleteUnit` |
| Java | `client.organizationPeople.deleteUnit` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `unit_id` | path | `PathVar[str]` | Yes | Not specified |
| `expected_revision` | query | `QueryParam[int]` | Yes | Not specified |

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

<!-- operation: OrganizationPeopleController.settings -->
<a id="organizationpeoplecontroller-settings"></a>
## Settings

```http
GET /api/v1/tenants/{tenant_id}/organization/directory-settings
```

Contract operation: `OrganizationPeopleController.settings`.

| SDK | Method |
| --- | --- |
| Python | `organization_directory_settings` |
| TypeScript | `organizationPeople.settings` |
| Java | `client.organizationPeople.settings` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OrganizationDirectorySettings`](../models/organizationdirectorysettings.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.update_settings -->
<a id="organizationpeoplecontroller-update-settings"></a>
## Update settings

```http
PATCH /api/v1/tenants/{tenant_id}/organization/directory-settings
```

Contract operation: `OrganizationPeopleController.update_settings`.

| SDK | Method |
| --- | --- |
| Python | `update_organization_directory_settings` |
| TypeScript | `organizationPeople.updateSettings` |
| Java | `client.organizationPeople.updateSettings` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[OrganizationDirectorySettingsInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`OrganizationDirectorySettingsInput`](../models/organizationdirectorysettingsinput.md) |
| Response schema | [`OrganizationDirectorySettings`](../models/organizationdirectorysettings.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.mapping -->
<a id="organizationpeoplecontroller-mapping"></a>
## Mapping

```http
GET /api/v1/tenants/{tenant_id}/organization/profile-mappings/{provider_id}
```

Contract operation: `OrganizationPeopleController.mapping`.

| SDK | Method |
| --- | --- |
| Python | `organization_profile_mapping` |
| TypeScript | `organizationPeople.mapping` |
| Java | `client.organizationPeople.mapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OrganizationProfileMapping`](../models/organizationprofilemapping.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationPeopleController.update_mapping -->
<a id="organizationpeoplecontroller-update-mapping"></a>
## Update mapping

```http
PUT /api/v1/tenants/{tenant_id}/organization/profile-mappings/{provider_id}
```

Contract operation: `OrganizationPeopleController.update_mapping`.

| SDK | Method |
| --- | --- |
| Python | `update_organization_profile_mapping` |
| TypeScript | `organizationPeople.updateMapping` |
| Java | `client.organizationPeople.updateMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[OrganizationProfileMappingInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`OrganizationProfileMappingInput`](../models/organizationprofilemappinginput.md) |
| Response schema | [`OrganizationProfileMapping`](../models/organizationprofilemapping.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
