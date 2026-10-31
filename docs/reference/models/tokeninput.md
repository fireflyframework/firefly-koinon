<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# TokenInput

[All wire models](index.md)

Model aliases: `TokenInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `scopes` | Array of `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `workspace_ids` | Array of `string` or `null` | No | `null` |
| `asset_ids` | Array of `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expires_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "scopes": {
          "items": {
            "type": "string"
          },
          "title": "Scopes",
          "type": "array"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
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
        }
      },
      "required": [
        "name",
        "tenant_id",
        "scopes",
        "expires_at"
      ],
      "title": "TokenInput",
      "type": "object"
    }
    ```
