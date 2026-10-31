<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Corporate identity

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [List](#corporateidentitycontroller-list) (GET)
- [Create](#corporateidentitycontroller-create) (POST)
- [Get](#corporateidentitycontroller-get) (GET)
- [Update](#corporateidentitycontroller-update) (PATCH)
- [Test](#corporateidentitycontroller-test) (POST)
- [Test status](#corporateidentitycontroller-test-status) (GET)
- [Groups](#corporateidentitycontroller-groups) (GET)
- [Mappings](#corporateidentitycontroller-mappings) (GET)
- [Mapping create](#corporateidentitycontroller-mapping-create) (POST)
- [Mapping update](#corporateidentitycontroller-mapping-update) (PATCH)
- [Mapping remove](#corporateidentitycontroller-mapping-remove) (DELETE)
- [Activate](#corporateidentitycontroller-activate) (POST)
- [Disable](#corporateidentitycontroller-disable) (POST)

<!-- operation: CorporateIdentityController.list -->
<a id="corporateidentitycontroller-list"></a>
## List

```http
GET /api/v1/tenants/{tenant_id}/identity/providers
```

Contract operation: `CorporateIdentityController.list`.

| SDK | Method |
| --- | --- |
| Python | `identity_providers` |
| TypeScript | `identity.list` |
| Java | `client.identity.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `kind` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `status` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`IdentityProviderPage`](../models/identityproviderpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.create -->
<a id="corporateidentitycontroller-create"></a>
## Create

```http
POST /api/v1/tenants/{tenant_id}/identity/providers
```

Contract operation: `CorporateIdentityController.create`.

| SDK | Method |
| --- | --- |
| Python | `create_identity_provider` |
| TypeScript | `identity.create` |
| Java | `client.identity.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IdentityProviderInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IdentityProviderInput`](../models/identityproviderinput.md) |
| Response schema | [`IdentityProvider`](../models/identityprovider.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.get -->
<a id="corporateidentitycontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}
```

Contract operation: `CorporateIdentityController.get`.

| SDK | Method |
| --- | --- |
| Python | `identity_provider` |
| TypeScript | `identity.get` |
| Java | `client.identity.get` |

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
| Response schema | [`IdentityProvider`](../models/identityprovider.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.update -->
<a id="corporateidentitycontroller-update"></a>
## Update

```http
PATCH /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}
```

Contract operation: `CorporateIdentityController.update`.

| SDK | Method |
| --- | --- |
| Python | `update_identity_provider` |
| TypeScript | `identity.update` |
| Java | `client.identity.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IdentityProviderPatch]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IdentityProviderPatch`](../models/identityproviderpatch.md) |
| Response schema | [`IdentityProvider`](../models/identityprovider.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.test -->
<a id="corporateidentitycontroller-test"></a>
## Test

```http
POST /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/test
```

Contract operation: `CorporateIdentityController.test`.

| SDK | Method |
| --- | --- |
| Python | `test_identity_provider` |
| TypeScript | `identity.test` |
| Java | `client.identity.test` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IdentityRevision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IdentityRevision`](../models/identityrevision.md) |
| Response schema | [`IdentityValidation`](../models/identityvalidation.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.test_status -->
<a id="corporateidentitycontroller-test-status"></a>
## Test status

```http
GET /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/tests/{validation_id}
```

Contract operation: `CorporateIdentityController.test_status`.

| SDK | Method |
| --- | --- |
| Python | `identity_test_status` |
| TypeScript | `identity.testStatus` |
| Java | `client.identity.testStatus` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `validation_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`IdentityValidation`](../models/identityvalidation.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.groups -->
<a id="corporateidentitycontroller-groups"></a>
## Groups

```http
GET /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/groups
```

Contract operation: `CorporateIdentityController.groups`.

| SDK | Method |
| --- | --- |
| Python | `identity_groups` |
| TypeScript | `identity.groups` |
| Java | `client.identity.groups` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `limit` | query | `QueryParam[int]` | No | `25` |
| `after` | query | `QueryParam[str]` | No | `""` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`IdentityGroupPage`](../models/identitygrouppage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.mappings -->
<a id="corporateidentitycontroller-mappings"></a>
## Mappings

```http
GET /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/mappings
```

Contract operation: `CorporateIdentityController.mappings`.

| SDK | Method |
| --- | --- |
| Python | `identity_mappings` |
| TypeScript | `identity.mappings` |
| Java | `client.identity.mappings` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `status` | query | `QueryParam[str]` | No | `"all"` |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`IdentityMappingPage`](../models/identitymappingpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.mapping_create -->
<a id="corporateidentitycontroller-mapping-create"></a>
## Mapping create

```http
POST /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/mappings
```

Contract operation: `CorporateIdentityController.mapping_create`.

| SDK | Method |
| --- | --- |
| Python | `create_identity_mapping` |
| TypeScript | `identity.createMapping` |
| Java | `client.identity.createMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IdentityMappingInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IdentityMappingInput`](../models/identitymappinginput.md) |
| Response schema | [`IdentityMapping`](../models/identitymapping.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.mapping_update -->
<a id="corporateidentitycontroller-mapping-update"></a>
## Mapping update

```http
PATCH /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/mappings/{mapping_id}
```

Contract operation: `CorporateIdentityController.mapping_update`.

| SDK | Method |
| --- | --- |
| Python | `update_identity_mapping` |
| TypeScript | `identity.updateMapping` |
| Java | `client.identity.updateMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IdentityMappingInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IdentityMappingInput`](../models/identitymappinginput.md) |
| Response schema | [`IdentityMapping`](../models/identitymapping.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.mapping_remove -->
<a id="corporateidentitycontroller-mapping-remove"></a>
## Mapping remove

```http
DELETE /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/mappings/{mapping_id}
```

Contract operation: `CorporateIdentityController.mapping_remove`.

| SDK | Method |
| --- | --- |
| Python | `remove_identity_mapping` |
| TypeScript | `identity.removeMapping` |
| Java | `client.identity.removeMapping` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `mapping_id` | path | `PathVar[str]` | Yes | Not specified |
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

<!-- operation: CorporateIdentityController.activate -->
<a id="corporateidentitycontroller-activate"></a>
## Activate

```http
POST /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/activate
```

Contract operation: `CorporateIdentityController.activate`.

| SDK | Method |
| --- | --- |
| Python | `activate_identity_provider` |
| TypeScript | `identity.activate` |
| Java | `client.identity.activate` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IdentityActivation]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IdentityActivation`](../models/identityactivation.md) |
| Response schema | [`IdentityProvider`](../models/identityprovider.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: CorporateIdentityController.disable -->
<a id="corporateidentitycontroller-disable"></a>
## Disable

```http
POST /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/disable
```

Contract operation: `CorporateIdentityController.disable`.

| SDK | Method |
| --- | --- |
| Python | `disable_identity_provider` |
| TypeScript | `identity.disable` |
| Java | `client.identity.disable` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[IdentityRevision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`IdentityRevision`](../models/identityrevision.md) |
| Response schema | [`IdentityProvider`](../models/identityprovider.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
