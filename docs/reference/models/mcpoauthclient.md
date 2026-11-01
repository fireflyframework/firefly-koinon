<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpOAuthClient

[All wire models](index.md)

Model aliases: `McpOAuthClient`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Not specified |
| `redirect_uris` | Array of `string` | Yes | Not specified |
| `scopes` | Array of `string` | Yes | Not specified |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `client_id` | `string` | Yes | Not specified |
| `client_type` | `string` | Yes | Not specified |
| `enabled` | `boolean` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |
| `created_by` | `string` | Yes | Not specified |
| `updated_by` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### name

- Minimum length: `1`
- Maximum length: `120`

### redirect_uris

- Minimum items: `1`
- Maximum items: `8`

### scopes

- Minimum items: `1`
- Maximum items: `8`
- Each item: Allowed values: `"catalog:read"`, `"catalog:write"`, `"ingest:write"`, `"knowledge:search"`, `"query:execute"`, `"chat:use"`, `"evidence:read"`, `"activity:read"`

### client_type

- Allowed values: `"public"`, `"confidential"`

### created_at

- Format: `"date-time"`

### updated_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "redirect_uris": {
          "items": {
            "type": "string"
          },
          "maxItems": 8,
          "minItems": 1,
          "title": "Redirect Uris",
          "type": "array"
        },
        "scopes": {
          "items": {
            "enum": [
              "catalog:read",
              "catalog:write",
              "ingest:write",
              "knowledge:search",
              "query:execute",
              "chat:use",
              "evidence:read",
              "activity:read"
            ],
            "type": "string"
          },
          "maxItems": 8,
          "minItems": 1,
          "title": "Scopes",
          "type": "array"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "client_id": {
          "title": "Client Id",
          "type": "string"
        },
        "client_type": {
          "enum": [
            "public",
            "confidential"
          ],
          "title": "Client Type",
          "type": "string"
        },
        "enabled": {
          "title": "Enabled",
          "type": "boolean"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "updated_at": {
          "format": "date-time",
          "title": "Updated At",
          "type": "string"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "updated_by": {
          "title": "Updated By",
          "type": "string"
        }
      },
      "required": [
        "name",
        "redirect_uris",
        "scopes",
        "id",
        "tenant_id",
        "client_id",
        "client_type",
        "enabled",
        "revision",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by"
      ],
      "title": "McpOAuthClient",
      "type": "object"
    }
    ```
