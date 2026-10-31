<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationDirectorySettings

[All wire models](index.md)

Model aliases: `OrganizationDirectorySettings`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `visibility` | `string` | No | `"administrators"` |
| `revision` | `integer` | No | `0` |

## Model constraints

- Additional properties: permitted

## Field constraints

### visibility

- Allowed values: `"administrators"`, `"shared_workspaces"`

### revision

- Minimum: `0`
- Maximum: `2147483647`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "visibility": {
          "default": "administrators",
          "enum": [
            "administrators",
            "shared_workspaces"
          ],
          "title": "Visibility",
          "type": "string"
        },
        "revision": {
          "default": 0,
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Revision",
          "type": "integer"
        }
      },
      "required": [
        "tenant_id"
      ],
      "title": "OrganizationDirectorySettings",
      "type": "object"
    }
    ```
