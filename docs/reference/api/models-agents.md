<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Models and agents

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Agents](#agentcontroller-agents) (GET)
- [Agent create](#agentcontroller-agent-create) (POST)
- [Agent update](#agentcontroller-agent-update) (PATCH)
- [Agent validate](#agentcontroller-agent-validate) (POST)
- [Configuration](#providercontroller-configuration) (GET)
- [Provider create](#providercontroller-provider-create) (POST)
- [Provider update](#providercontroller-provider-update) (PUT)
- [Provider validate](#providercontroller-provider-validate) (POST)

<!-- operation: AgentController.agents -->
<a id="agentcontroller-agents"></a>
## Agents

```http
GET /api/v1/tenants/{tenant_id}/agents
```

Contract operation: `AgentController.agents`.

| SDK | Method |
| --- | --- |
| Python | `agents` |
| TypeScript | `agents.list` |
| Java | `client.agents.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |
| `status` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `project_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `sort` | query | `QueryParam[str]` | No | `"name"` |
| `order` | query | `QueryParam[str]` | No | `"asc"` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[AgentConfiguration]`](../models/page-agentconfiguration.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AgentController.agent_create -->
<a id="agentcontroller-agent-create"></a>
## Agent create

```http
POST /api/v1/tenants/{tenant_id}/agents
```

Contract operation: `AgentController.agent_create`.

| SDK | Method |
| --- | --- |
| Python | `create_agent` |
| TypeScript | `agents.create` |
| Java | `client.agents.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[AgentInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`AgentInput`](../models/agentinput.md) |
| Response schema | [`AgentConfiguration`](../models/agentconfiguration.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AgentController.agent_update -->
<a id="agentcontroller-agent-update"></a>
## Agent update

```http
PATCH /api/v1/tenants/{tenant_id}/agents/{agent_id}
```

Contract operation: `AgentController.agent_update`.

| SDK | Method |
| --- | --- |
| Python | `update_agent` |
| TypeScript | `agents.update` |
| Java | `client.agents.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `agent_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[AgentInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`AgentInput`](../models/agentinput.md) |
| Response schema | [`AgentConfiguration`](../models/agentconfiguration.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AgentController.agent_validate -->
<a id="agentcontroller-agent-validate"></a>
## Agent validate

```http
POST /api/v1/tenants/{tenant_id}/agents/{agent_id}/validate
```

Contract operation: `AgentController.agent_validate`.

| SDK | Method |
| --- | --- |
| Python | `validate_agent` |
| TypeScript | `agents.validate` |
| Java | `client.agents.validate` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `agent_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`AgentConfiguration`](../models/agentconfiguration.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ProviderController.configuration -->
<a id="providercontroller-configuration"></a>
## Configuration

```http
GET /api/v1/tenants/{tenant_id}/configuration
```

Contract operation: `ProviderController.configuration`.

| SDK | Method |
| --- | --- |
| Python | `configuration` |
| TypeScript | `configuration.get` |
| Java | `client.configuration.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Configuration`](../models/configuration.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ProviderController.provider_create -->
<a id="providercontroller-provider-create"></a>
## Provider create

```http
POST /api/v1/tenants/{tenant_id}/providers
```

Contract operation: `ProviderController.provider_create`.

| SDK | Method |
| --- | --- |
| Python | `create_provider` |
| TypeScript | `providers.create` |
| Java | `client.providers.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ProviderInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ProviderInput`](../models/providerinput.md) |
| Response schema | [`ModelProvider`](../models/modelprovider.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ProviderController.provider_update -->
<a id="providercontroller-provider-update"></a>
## Provider update

```http
PUT /api/v1/tenants/{tenant_id}/providers/{provider_id}
```

Contract operation: `ProviderController.provider_update`.

| SDK | Method |
| --- | --- |
| Python | `update_provider` |
| TypeScript | `providers.update` |
| Java | `client.providers.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `provider_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ProviderInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ProviderInput`](../models/providerinput.md) |
| Response schema | [`ModelProvider`](../models/modelprovider.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ProviderController.provider_validate -->
<a id="providercontroller-provider-validate"></a>
## Provider validate

```http
POST /api/v1/tenants/{tenant_id}/providers/{provider_id}/validate
```

Contract operation: `ProviderController.provider_validate`.

| SDK | Method |
| --- | --- |
| Python | `validate_provider` |
| TypeScript | `providers.validate` |
| Java | `client.providers.validate` |

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
| Response schema | [`ValidationResult`](../models/validationresult.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
