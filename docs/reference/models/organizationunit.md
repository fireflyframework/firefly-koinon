<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationUnit

[All wire models](index.md)

Model aliases: `OrganizationUnit`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `updated_at` | `string` or `null` | No | `null` |
| `tenant_id` | `string` | Yes | Not specified |
| `parent_id` | `string` or `null` | No | `null` |
| `revision` | `integer` | Yes | Not specified |
| `provider_id` | `string` or `null` | No | `null` |
| `has_children` | `boolean` | No | `false` |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"division"`, `"department"`, `"team"`

### updated_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### revision

- Minimum: `1`
- Maximum: `2147483647`


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
        "kind": {
          "enum": [
            "division",
            "department",
            "team"
          ],
          "title": "Kind",
          "type": "string"
        },
        "updated_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Updated At"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "parent_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Id"
        },
        "revision": {
          "maximum": 2147483647,
          "minimum": 1,
          "title": "Revision",
          "type": "integer"
        },
        "provider_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Provider Id"
        },
        "has_children": {
          "default": false,
          "title": "Has Children",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "name",
        "kind",
        "tenant_id",
        "revision"
      ],
      "title": "OrganizationUnit",
      "type": "object"
    }
    ```
