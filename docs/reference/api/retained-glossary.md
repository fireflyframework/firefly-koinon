<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Retained glossary API

[API and SDK index](../sdk-api.md#qualified-retained-glossary-api)

These qualified retained operations are separate from the canonical count. SDK mappings, schemas and headers come from the manifest. Parameter signatures and success statuses are read from the matching native controller source; generation rejects a controller or admission guard whose digest differs from the manifest. HTTP mappings without an explicit status use the native framework default of 200. The structured module and its native datasource must be configured.

Pass the canonical tenant and workspace through `X-Tenant-ID` and `X-Workspace-ID`. For updates and deletion, preserve the exact returned `updated_at` string, including microseconds and its offset, for the `If-Match` precondition. List totals can be unknown; honor the returned `limit`, `offset` and `has_more`.

<!-- compatibility-operation: GlossaryController.list_terms -->
<a id="glossarycontroller-list-terms"></a>
## GlossaryController.list_terms

```http
GET /api/v1/structured/glossary
```

| SDK | Method |
| --- | --- |
| Python | `glossary_terms` |
| TypeScript | `structured.glossary.list` |
| Java | `client.structuredGlossary(tenant,workspace).list` |

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`GlossaryPage`](../models/glossarypage.md) |
| Success status | `200` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `limit` | query | `QueryParam[int]` | No | `100` |
| `offset` | query | `QueryParam[int]` | No | `0` |

<!-- compatibility-operation: GlossaryController.get_term -->
<a id="glossarycontroller-get-term"></a>
## GlossaryController.get_term

```http
GET /api/v1/structured/glossary/{term_id}
```

| SDK | Method |
| --- | --- |
| Python | `glossary_term` |
| TypeScript | `structured.glossary.get` |
| Java | `client.structuredGlossary(tenant,workspace).get` |

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`GlossaryTermRead`](../models/glossarytermread.md) |
| Success status | `200` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `term_id` | path | `PathVar[uuid.UUID]` | Yes | Not specified |

<!-- compatibility-operation: GlossaryController.create -->
<a id="glossarycontroller-create"></a>
## GlossaryController.create

```http
POST /api/v1/structured/glossary
```

| SDK | Method |
| --- | --- |
| Python | `create_glossary_term` |
| TypeScript | `structured.glossary.create` |
| Java | `client.structuredGlossary(tenant,workspace).create` |

| Contract | Value |
| --- | --- |
| Request schema | [`GlossaryTermCreate`](../models/glossarytermcreate.md) |
| Response schema | [`GlossaryTermRead`](../models/glossarytermread.md) |
| Success status | `201` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `body` | body | `Valid[Body[GlossaryTermCreate]]` | Yes | Not specified |

<!-- compatibility-operation: GlossaryController.update -->
<a id="glossarycontroller-update"></a>
## GlossaryController.update

```http
PUT /api/v1/structured/glossary/{term_id}
```

| SDK | Method |
| --- | --- |
| Python | `update_glossary_term` |
| TypeScript | `structured.glossary.update` |
| Java | `client.structuredGlossary(tenant,workspace).update` |

| Contract | Value |
| --- | --- |
| Request schema | [`GlossaryTermUpdate`](../models/glossarytermupdate.md) |
| Response schema | [`GlossaryTermRead`](../models/glossarytermread.md) |
| Success status | `200` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`
- `If-Match (exact unparsed updated_at string)`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `term_id` | path | `PathVar[uuid.UUID]` | Yes | Not specified |
| `body` | body | `Valid[Body[GlossaryTermUpdate]]` | Yes | Not specified |
| `If-Match` | header | `str` | Yes | Not specified |

<!-- compatibility-operation: GlossaryController.delete -->
<a id="glossarycontroller-delete"></a>
## GlossaryController.delete

```http
DELETE /api/v1/structured/glossary/{term_id}
```

| SDK | Method |
| --- | --- |
| Python | `delete_glossary_term` |
| TypeScript | `structured.glossary.remove` |
| Java | `client.structuredGlossary(tenant,workspace).remove` |

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | No response body |
| Success status | `204` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`
- `If-Match (exact unparsed updated_at string)`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `term_id` | path | `PathVar[uuid.UUID]` | Yes | Not specified |
| `If-Match` | header | `str` | Yes | Not specified |

<!-- compatibility-operation: AgentGlossaryController.list_terms -->
<a id="agentglossarycontroller-list-terms"></a>
## AgentGlossaryController.list_terms

```http
GET /api/v1/structured/agent/glossary
```

| SDK | Method |
| --- | --- |
| Python | `glossary_terms(agent=True)` |
| TypeScript | `structured.agentGlossary.list` |
| Java | `client.structuredAgentGlossary(tenant,workspace).list` |

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`GlossaryPage`](../models/glossarypage.md) |
| Success status | `200` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `limit` | query | `QueryParam[int]` | No | `100` |
| `offset` | query | `QueryParam[int]` | No | `0` |

<!-- compatibility-operation: AgentGlossaryController.get_term -->
<a id="agentglossarycontroller-get-term"></a>
## AgentGlossaryController.get_term

```http
GET /api/v1/structured/agent/glossary/{term_id}
```

| SDK | Method |
| --- | --- |
| Python | `glossary_term(agent=True)` |
| TypeScript | `structured.agentGlossary.get` |
| Java | `client.structuredAgentGlossary(tenant,workspace).get` |

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`GlossaryTermRead`](../models/glossarytermread.md) |
| Success status | `200` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `term_id` | path | `PathVar[uuid.UUID]` | Yes | Not specified |

<!-- compatibility-operation: AgentGlossaryController.create -->
<a id="agentglossarycontroller-create"></a>
## AgentGlossaryController.create

```http
POST /api/v1/structured/agent/glossary
```

| SDK | Method |
| --- | --- |
| Python | `create_glossary_term(agent=True)` |
| TypeScript | `structured.agentGlossary.create` |
| Java | `client.structuredAgentGlossary(tenant,workspace).create` |

| Contract | Value |
| --- | --- |
| Request schema | [`GlossaryTermCreate`](../models/glossarytermcreate.md) |
| Response schema | [`GlossaryTermRead`](../models/glossarytermread.md) |
| Success status | `201` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `body` | body | `Valid[Body[GlossaryTermCreate]]` | Yes | Not specified |

<!-- compatibility-operation: AgentGlossaryController.update -->
<a id="agentglossarycontroller-update"></a>
## AgentGlossaryController.update

```http
PUT /api/v1/structured/agent/glossary/{term_id}
```

| SDK | Method |
| --- | --- |
| Python | `update_glossary_term(agent=True)` |
| TypeScript | `structured.agentGlossary.update` |
| Java | `client.structuredAgentGlossary(tenant,workspace).update` |

| Contract | Value |
| --- | --- |
| Request schema | [`GlossaryTermUpdate`](../models/glossarytermupdate.md) |
| Response schema | [`GlossaryTermRead`](../models/glossarytermread.md) |
| Success status | `200` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`
- `If-Match (exact unparsed updated_at string)`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `term_id` | path | `PathVar[uuid.UUID]` | Yes | Not specified |
| `body` | body | `Valid[Body[GlossaryTermUpdate]]` | Yes | Not specified |
| `If-Match` | header | `str` | Yes | Not specified |

<!-- compatibility-operation: AgentGlossaryController.delete -->
<a id="agentglossarycontroller-delete"></a>
## AgentGlossaryController.delete

```http
DELETE /api/v1/structured/agent/glossary/{term_id}
```

| SDK | Method |
| --- | --- |
| Python | `delete_glossary_term(agent=True)` |
| TypeScript | `structured.agentGlossary.remove` |
| Java | `client.structuredAgentGlossary(tenant,workspace).remove` |

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | No response body |
| Success status | `204` |
| Encoding | `application/json` |

### Headers

- `X-Tenant-ID`
- `X-Workspace-ID`
- `If-Match (exact unparsed updated_at string)`

### Parameters

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `X-Tenant-ID` | header | `str` | Yes | Not specified |
| `X-Workspace-ID` | header | `str` | Yes | Not specified |
| `term_id` | path | `PathVar[uuid.UUID]` | Yes | Not specified |
| `If-Match` | header | `str` | Yes | Not specified |
