<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AuthorizedApplication

[All wire models](index.md)

Model aliases: `AuthorizedApplication`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `client_id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `resource` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `tenant_name` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `workspace_name` | `string` | Yes | Not specified |
| `scopes` | Array of `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `connected_at` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `last_used_at` | `string` or `null` | Yes | Not specified |
| `revoked_at` | `string` or `null` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"active"`, `"expired"`, `"revoked"`

### connected_at

- Format: `"date-time"`

### expires_at

- Format: `"date-time"`

### last_used_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### revoked_at

- anyOf branch 1 (`string`): Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "client_id": {
          "title": "Client Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "resource": {
          "title": "Resource",
          "type": "string"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "tenant_name": {
          "title": "Tenant Name",
          "type": "string"
        },
        "workspace_id": {
          "title": "Workspace Id",
          "type": "string"
        },
        "workspace_name": {
          "title": "Workspace Name",
          "type": "string"
        },
        "scopes": {
          "items": {
            "type": "string"
          },
          "title": "Scopes",
          "type": "array"
        },
        "status": {
          "enum": [
            "active",
            "expired",
            "revoked"
          ],
          "title": "Status",
          "type": "string"
        },
        "connected_at": {
          "format": "date-time",
          "title": "Connected At",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        },
        "last_used_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Last Used At"
        },
        "revoked_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Revoked At"
        }
      },
      "required": [
        "id",
        "client_id",
        "name",
        "resource",
        "tenant_id",
        "tenant_name",
        "workspace_id",
        "workspace_name",
        "scopes",
        "status",
        "connected_at",
        "expires_at",
        "last_used_at",
        "revoked_at"
      ],
      "title": "AuthorizedApplication",
      "type": "object"
    }
    ```
