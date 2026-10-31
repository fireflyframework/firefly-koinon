<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeConnection

[All wire models](index.md)

Model aliases: `KnowledgeConnection`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | No | `null` |
| `domain` | `string` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `mode` | `string` | Yes | Not specified |
| `provider_id` | `string` or `null` | No | `null` |
| `model_id` | `string` or `null` | No | `null` |
| `model_options` | Map of string keys to [`JsonValue`](jsonvalue.md) | Yes | Not specified |
| `dimensions` | `integer` or `null` | No | `null` |
| `storage_dimensions` | `integer` or `null` | No | `null` |
| `space_id` | `string` or `null` | No | `null` |
| `embedding_fingerprint` | `string` or `null` | No | `null` |
| `enabled` | `boolean` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `created_by` | `string` | Yes | Not specified |
| `updated_by` | `string` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### domain

- Allowed values: `"documents"`, `"structured"`

### mode

- Allowed values: `"provider"`, `"current_agent"`

### model_options

- Additional properties: [`JsonValue`](jsonvalue.md)


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
        "domain": {
          "enum": [
            "documents",
            "structured"
          ],
          "title": "Domain",
          "type": "string"
        },
        "role": {
          "title": "Role",
          "type": "string"
        },
        "mode": {
          "enum": [
            "provider",
            "current_agent"
          ],
          "title": "Mode",
          "type": "string"
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
        "model_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Model Id"
        },
        "model_options": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Model Options",
          "type": "object"
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
          "default": null,
          "title": "Dimensions"
        },
        "storage_dimensions": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Storage Dimensions"
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
          "default": null,
          "title": "Space Id"
        },
        "embedding_fingerprint": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Embedding Fingerprint"
        },
        "enabled": {
          "title": "Enabled",
          "type": "boolean"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "updated_by": {
          "title": "Updated By",
          "type": "string"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "updated_at": {
          "title": "Updated At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "domain",
        "role",
        "mode",
        "model_options",
        "enabled",
        "revision",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at"
      ],
      "title": "KnowledgeConnection",
      "type": "object"
    }
    ```
