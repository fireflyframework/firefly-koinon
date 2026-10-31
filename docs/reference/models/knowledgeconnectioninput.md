<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeConnectionInput

[All wire models](index.md)

Model aliases: `KnowledgeConnectionInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `domain` | `string` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | No | `null` |
| `mode` | `string` | No | `"provider"` |
| `provider_id` | `string` or `null` | No | `null` |
| `model_id` | `string` or `null` | No | `null` |
| `model_options` | [`ModelParameters`](modelparameters.md) or `null` | No | `null` |
| `dimensions` | `integer` or `null` | No | `null` |
| `storage_dimensions` | `integer` or `null` | No | `null` |
| `space_id` | `string` or `null` | No | `null` |
| `enabled` | `boolean` | No | `true` |
| `expected_revision` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### domain

- Allowed values: `"documents"`, `"structured"`

### mode

- Allowed values: `"provider"`, `"current_agent"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
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
        "mode": {
          "default": "provider",
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
          "anyOf": [
            {
              "$ref": "#/$defs/ModelParameters"
            },
            {
              "type": "null"
            }
          ],
          "default": null
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
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "expected_revision": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Revision"
        }
      },
      "required": [
        "domain",
        "role"
      ],
      "title": "KnowledgeConnectionInput",
      "type": "object"
    }
    ```
