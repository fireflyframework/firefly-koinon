<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# PromotedCatalogEntry

[All wire models](index.md)

Model aliases: `PromotedCatalogEntry`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `parent_id` | `string` or `null` | Yes | Not specified |
| `workspace_id` | `string` or `null` | Yes | Not specified |
| `project_id` | `string` or `null` | Yes | Not specified |
| `description` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `created_by` | `string` | Yes | Not specified |
| `updated_by` | `string` | Yes | Not specified |
| `metadata` | Map of string keys to [`JsonValue`](jsonvalue.md) | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### metadata

- Additional properties: [`JsonValue`](jsonvalue.md)

### created_at

- Format: `"date-time"`

### updated_at

- Format: `"date-time"`


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
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "kind": {
          "title": "Kind",
          "type": "string"
        },
        "name": {
          "title": "Name",
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
          "title": "Parent Id"
        },
        "workspace_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Workspace Id"
        },
        "project_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Project Id"
        },
        "description": {
          "title": "Description",
          "type": "string"
        },
        "status": {
          "title": "Status",
          "type": "string"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "updated_by": {
          "title": "Updated By",
          "type": "string"
        },
        "metadata": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Metadata",
          "type": "object"
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
        }
      },
      "required": [
        "id",
        "tenant_id",
        "kind",
        "name",
        "parent_id",
        "workspace_id",
        "project_id",
        "description",
        "status",
        "created_by",
        "updated_by",
        "metadata",
        "created_at",
        "updated_at"
      ],
      "title": "PromotedCatalogEntry",
      "type": "object"
    }
    ```
