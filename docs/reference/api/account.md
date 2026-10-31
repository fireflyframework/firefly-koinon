<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Personal profiles and tokens

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Get](#profilecontroller-get) (GET)
- [Update](#profilecontroller-update) (PATCH)
- [Avatar](#profilecontroller-avatar) (GET)
- [Set avatar](#profilecontroller-set-avatar) (POST)
- [Delete avatar](#profilecontroller-delete-avatar) (DELETE)
- [People](#profilecontroller-people) (GET)
- [Person avatar](#profilecontroller-person-avatar) (GET)
- [List](#personaltokencontroller-list) (GET)
- [Scopes](#personaltokencontroller-scopes) (GET)
- [Create](#personaltokencontroller-create) (POST)
- [Revoke](#personaltokencontroller-revoke) (DELETE)

<!-- operation: ProfileController.get -->
<a id="profilecontroller-get"></a>
## Get

```http
GET /api/v1/profile
```

Contract operation: `ProfileController.get`.

| SDK | Method |
| --- | --- |
| Python | `profile` |
| TypeScript | `profile.get` |
| Java | `client.profile.get` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`UserProfile`](../models/userprofile.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ProfileController.update -->
<a id="profilecontroller-update"></a>
## Update

```http
PATCH /api/v1/profile
```

Contract operation: `ProfileController.update`.

| SDK | Method |
| --- | --- |
| Python | `update_profile` |
| TypeScript | `profile.update` |
| Java | `client.profile.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `body` | body | `Valid[Body[ProfileInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ProfileUpdate`](../models/profileupdate.md) |
| Response schema | [`UserProfile`](../models/userprofile.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ProfileController.avatar -->
<a id="profilecontroller-avatar"></a>
## Avatar

```http
GET /api/v1/profile/avatar
```

Contract operation: `ProfileController.avatar`.

| SDK | Method |
| --- | --- |
| Python | `avatar_download` |
| TypeScript | `profile.avatarDownload` |
| Java | `client.profile.avatar` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

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

<!-- operation: ProfileController.set_avatar -->
<a id="profilecontroller-set-avatar"></a>
## Set avatar

```http
POST /api/v1/profile/avatar
```

Contract operation: `ProfileController.set_avatar`.

| SDK | Method |
| --- | --- |
| Python | `set_avatar` |
| TypeScript | `profile.uploadAvatar` |
| Java | `client.profile.uploadAvatar` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`AvatarUpload`](../models/avatarupload.md) |
| Response schema | [`UserProfile`](../models/userprofile.md) |
| Success status | `200` |
| Declared encoding | <code>image&#47;png&#124;image&#47;jpeg&#124;image&#47;webp</code> |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ProfileController.delete_avatar -->
<a id="profilecontroller-delete-avatar"></a>
## Delete avatar

```http
DELETE /api/v1/profile/avatar
```

Contract operation: `ProfileController.delete_avatar`.

| SDK | Method |
| --- | --- |
| Python | `delete_avatar` |
| TypeScript | `profile.deleteAvatar` |
| Java | `client.profile.deleteAvatar` |

### Parameters

No path, query or body arguments are declared in the canonical operation metadata.

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`UserProfile`](../models/userprofile.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ProfileController.people -->
<a id="profilecontroller-people"></a>
## People

```http
GET /api/v1/tenants/{tenant_id}/people
```

Contract operation: `ProfileController.people`.

| SDK | Method |
| --- | --- |
| Python | `people` |
| TypeScript | `people.list` |
| Java | `client.people.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `q` | query | `QueryParam[str]` | No | `""` |
| `limit` | query | `QueryParam[int]` | No | `20` |
| `after` | query | `QueryParam[str]` | No | `""` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[Person]`](../models/page-person.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ProfileController.person_avatar -->
<a id="profilecontroller-person-avatar"></a>
## Person avatar

```http
GET /api/v1/tenants/{tenant_id}/people/{profile_id}/avatar
```

Contract operation: `ProfileController.person_avatar`.

| SDK | Method |
| --- | --- |
| Python | `person_avatar` |
| TypeScript | `people.avatar` |
| Java | `client.people.avatar` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `profile_id` | path | `PathVar[str]` | Yes | Not specified |
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

<!-- operation: PersonalTokenController.list -->
<a id="personaltokencontroller-list"></a>
## List

```http
GET /api/v1/tokens
```

Contract operation: `PersonalTokenController.list`.

| SDK | Method |
| --- | --- |
| Python | `tokens` |
| TypeScript | `tokens.list` |
| Java | `client.tokens.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `q` | query | `QueryParam[str]` | No | `""` |
| `status` | query | `QueryParam[str]` | No | `"all"` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |
| `sort` | query | `QueryParam[str]` | No | `"created_at"` |
| `order` | query | `QueryParam[str]` | No | `"desc"` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[PersonalToken]`](../models/page-personaltoken.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: PersonalTokenController.scopes -->
<a id="personaltokencontroller-scopes"></a>
## Scopes

```http
GET /api/v1/tokens/scopes
```

Contract operation: `PersonalTokenController.scopes`.

| SDK | Method |
| --- | --- |
| Python | `token_scopes` |
| TypeScript | `tokens.scopes` |
| Java | `client.tokens.scopes` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | query | `QueryParam[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`TokenScopeOptions`](../models/tokenscopeoptions.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: PersonalTokenController.create -->
<a id="personaltokencontroller-create"></a>
## Create

```http
POST /api/v1/tokens
```

Contract operation: `PersonalTokenController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_token` |
| TypeScript | `tokens.create` |
| Java | `client.tokens.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `body` | body | `Valid[Body[TokenInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`TokenInput`](../models/tokeninput.md) |
| Response schema | [`TokenCreated`](../models/tokencreated.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: PersonalTokenController.revoke -->
<a id="personaltokencontroller-revoke"></a>
## Revoke

```http
DELETE /api/v1/tokens/{token_id}
```

Contract operation: `PersonalTokenController.revoke`.

| SDK | Method |
| --- | --- |
| Python | `revoke_token` |
| TypeScript | `tokens.revoke` |
| Java | `client.tokens.revoke` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `token_id` | path | `PathVar[str]` | Yes | Not specified |

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
