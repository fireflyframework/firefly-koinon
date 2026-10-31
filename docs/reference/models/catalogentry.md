<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CatalogEntry

[All wire models](index.md)

Model aliases: `CatalogEntry`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `created_by` | `string` or `null` | No | `null` |
| `updated_by` | `string` or `null` | No | `null` |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `parent_id` | `string` or `null` | No | `null` |
| `workspace_id` | `string` or `null` | No | `null` |
| `project_id` | `string` or `null` | No | `null` |
| `description` | `string` | No | `""` |
| `status` | `string` | Yes | Not specified |
| `metadata` | Map of string keys to [`JsonValue`](jsonvalue.md) | No | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### metadata

- Additional properties: [`JsonValue`](jsonvalue.md)


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "created_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created By"
        },
        "updated_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Updated By"
        },
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
          "default": null,
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
          "default": null,
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
          "default": null,
          "title": "Project Id"
        },
        "description": {
          "default": "",
          "title": "Description",
          "type": "string"
        },
        "status": {
          "title": "Status",
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
          "title": "Created At",
          "type": "string"
        },
        "updated_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Updated At"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "kind",
        "name",
        "status",
        "created_at"
      ],
      "title": "CatalogEntry",
      "type": "object"
    }
    ```
