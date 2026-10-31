<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NativeIndexChoice

[All wire models](index.md)

Model aliases: `NativeIndexChoice`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `domain` | `string` | Yes | Not specified |
| `native_id` | `string` | Yes | Not specified |
| `space_id` | `string` or `null` | Yes | Not specified |
| `provider_kind` | `string` or `null` | Yes | Not specified |
| `model_id` | `string` or `null` | Yes | Not specified |
| `dimensions` | `integer` or `null` | Yes | Not specified |
| `storage_dimensions` | `integer` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `active` | `boolean` | Yes | Not specified |
| `chunk_count` | `integer` | Yes | Not specified |
| `vector_count` | `integer` | Yes | Not specified |
| `indexed` | `boolean` or `null` | Yes | Not specified |
| `qualification` | `string` | Yes | Not specified |
| `managed_id` | `string` or `null` | No | `null` |
| `created_at` | `string` or `null` | No | `null` |
| `ready_at` | `string` or `null` | No | `null` |
| `activated_at` | `string` or `null` | No | `null` |
| `retired_at` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### domain

- Allowed values: `"documents"`, `"structured"`


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
        "workspace_id": {
          "title": "Workspace Id",
          "type": "string"
        },
        "domain": {
          "enum": [
            "documents",
            "structured"
          ],
          "title": "Domain",
          "type": "string"
        },
        "native_id": {
          "title": "Native Id",
          "type": "string"
        },
        "space_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Space Id"
        },
        "provider_kind": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Provider Kind"
        },
        "model_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Model Id"
        },
        "dimensions": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Dimensions"
        },
        "storage_dimensions": {
          "title": "Storage Dimensions",
          "type": "integer"
        },
        "status": {
          "title": "Status",
          "type": "string"
        },
        "active": {
          "title": "Active",
          "type": "boolean"
        },
        "chunk_count": {
          "title": "Chunk Count",
          "type": "integer"
        },
        "vector_count": {
          "title": "Vector Count",
          "type": "integer"
        },
        "indexed": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "title": "Indexed"
        },
        "qualification": {
          "title": "Qualification",
          "type": "string"
        },
        "managed_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Managed Id"
        },
        "created_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "ready_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ready At"
        },
        "activated_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Activated At"
        },
        "retired_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Retired At"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "workspace_id",
        "domain",
        "native_id",
        "space_id",
        "provider_kind",
        "model_id",
        "dimensions",
        "storage_dimensions",
        "status",
        "active",
        "chunk_count",
        "vector_count",
        "indexed",
        "qualification"
      ],
      "title": "NativeIndexChoice",
      "type": "object"
    }
    ```
