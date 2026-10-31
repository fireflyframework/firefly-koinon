<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# PersonalToken

[All wire models](index.md)

Model aliases: `PersonalToken`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `prefix` | `string` | Yes | Not specified |
| `scopes` | Array of `string` | Yes | Not specified |
| `workspace_ids` | Array of `string` or `null` | No | `null` |
| `asset_ids` | Array of `string` or `null` | No | `null` |
| `expires_at` | `string` | Yes | Not specified |
| `revoked_at` | `string` or `null` | No | `null` |
| `last_used_at` | `string` or `null` | No | `null` |
| `created_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

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
        "name": {
          "title": "Name",
          "type": "string"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "prefix": {
          "title": "Prefix",
          "type": "string"
        },
        "scopes": {
          "items": {
            "type": "string"
          },
          "title": "Scopes",
          "type": "array"
        },
        "workspace_ids": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Workspace Ids"
        },
        "asset_ids": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Asset Ids"
        },
        "expires_at": {
          "title": "Expires At",
          "type": "string"
        },
        "revoked_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Revoked At"
        },
        "last_used_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Used At"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "tenant_id",
        "prefix",
        "scopes",
        "expires_at",
        "created_at"
      ],
      "title": "PersonalToken",
      "type": "object"
    }
    ```
