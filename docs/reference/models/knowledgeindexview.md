<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeIndexView

[All wire models](index.md)

Model aliases: `KnowledgeIndexView`.

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
| `space_id` | `string` | Yes | Not specified |
| `provider_kind` | `string` | Yes | Not specified |
| `model_id` | `string` | Yes | Not specified |
| `dimensions` | `integer` | Yes | Not specified |
| `storage_dimensions` | `integer` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `active` | `boolean` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `job_id` | `string` or `null` | No | `null` |
| `chunk_count` | `integer` | Yes | Not specified |
| `vector_count` | `integer` | Yes | Not specified |
| `indexed` | `boolean` | Yes | Not specified |
| `qualification` | `string` | Yes | Not specified |
| `recovery_required` | `boolean` | No | `false` |
| `native_status` | `string` or `null` | No | `null` |
| `provider_id` | `string` or `null` | No | `null` |
| `created_by` | `string` or `null` | No | `null` |
| `updated_by` | `string` or `null` | No | `null` |
| `previous_space_id` | `string` or `null` | No | `null` |
| `created_at` | `string` or `null` | No | `null` |
| `ready_at` | `string` or `null` | No | `null` |
| `activated_at` | `string` or `null` | No | `null` |
| `retired_at` | `string` or `null` | No | `null` |
| `error_code` | `string` or `null` | No | `null` |
| `error` | `string` or `null` | No | `null` |

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
          "title": "Space Id",
          "type": "string"
        },
        "provider_kind": {
          "title": "Provider Kind",
          "type": "string"
        },
        "model_id": {
          "title": "Model Id",
          "type": "string"
        },
        "dimensions": {
          "title": "Dimensions",
          "type": "integer"
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
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "job_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Job Id"
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
          "title": "Indexed",
          "type": "boolean"
        },
        "qualification": {
          "title": "Qualification",
          "type": "string"
        },
        "recovery_required": {
          "default": false,
          "title": "Recovery Required",
          "type": "boolean"
        },
        "native_status": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Native Status"
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
        "previous_space_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Previous Space Id"
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
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Code"
        },
        "error": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error"
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
        "revision",
        "chunk_count",
        "vector_count",
        "indexed",
        "qualification"
      ],
      "title": "KnowledgeIndexView",
      "type": "object"
    }
    ```
