<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# TenantContext

[All wire models](index.md)

Model aliases: `TenantContext`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `roles` | Array of `string` | No | Not specified |
| `permissions` | Array of `string` | No | Not specified |

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
        "roles": {
          "items": {
            "type": "string"
          },
          "title": "Roles",
          "type": "array"
        },
        "permissions": {
          "items": {
            "type": "string"
          },
          "title": "Permissions",
          "type": "array"
        }
      },
      "required": [
        "id",
        "name"
      ],
      "title": "TenantContext",
      "type": "object"
    }
    ```
