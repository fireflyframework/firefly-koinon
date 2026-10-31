<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IndexPlanView

[All wire models](index.md)

Model aliases: `IndexPlanView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `domain` | `string` | Yes | Not specified |
| `provider_id` | `string` | Yes | Not specified |
| `provider_kind` | `string` | Yes | Not specified |
| `provider_revision` | `integer` | Yes | Not specified |
| `model_id` | `string` | Yes | Not specified |
| `dimensions` | `integer` | Yes | Not specified |
| `storage_dimensions` | `integer` | Yes | Not specified |
| `qualification` | `string` | Yes | Not specified |
| `expected_connection_revision` | `integer` or `null` | Yes | Not specified |
| `active_space_id` | `string` or `null` | Yes | Not specified |
| `active_index_id` | `string` or `null` | Yes | Not specified |
| `chunk_count` | `integer` | Yes | Not specified |
| `warnings` | Array of `string` | Yes | Not specified |

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
        "provider_id": {
          "title": "Provider Id",
          "type": "string"
        },
        "provider_kind": {
          "title": "Provider Kind",
          "type": "string"
        },
        "provider_revision": {
          "title": "Provider Revision",
          "type": "integer"
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
        "qualification": {
          "title": "Qualification",
          "type": "string"
        },
        "expected_connection_revision": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Expected Connection Revision"
        },
        "active_space_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Active Space Id"
        },
        "active_index_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Active Index Id"
        },
        "chunk_count": {
          "title": "Chunk Count",
          "type": "integer"
        },
        "warnings": {
          "items": {
            "type": "string"
          },
          "title": "Warnings",
          "type": "array"
        }
      },
      "required": [
        "tenant_id",
        "workspace_id",
        "domain",
        "provider_id",
        "provider_kind",
        "provider_revision",
        "model_id",
        "dimensions",
        "storage_dimensions",
        "qualification",
        "expected_connection_revision",
        "active_space_id",
        "active_index_id",
        "chunk_count",
        "warnings"
      ],
      "title": "IndexPlanView",
      "type": "object"
    }
    ```
