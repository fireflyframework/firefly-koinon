<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpToolCapability

[All wire models](index.md)

Model aliases: `McpToolCapability`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Not specified |
| `required_scopes` | Array of `string` | Yes | Not specified |
| `access` | `string` | Yes | Not specified |
| `requires_app` | `boolean` | No | `false` |

## Model constraints

- Additional properties: permitted

## Field constraints

### access

- Allowed values: `"read"`, `"query"`, `"proposal"`, `"app_only"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "required_scopes": {
          "items": {
            "type": "string"
          },
          "title": "Required Scopes",
          "type": "array"
        },
        "access": {
          "enum": [
            "read",
            "query",
            "proposal",
            "app_only"
          ],
          "title": "Access",
          "type": "string"
        },
        "requires_app": {
          "default": false,
          "title": "Requires App",
          "type": "boolean"
        }
      },
      "required": [
        "name",
        "required_scopes",
        "access"
      ],
      "title": "McpToolCapability",
      "type": "object"
    }
    ```
