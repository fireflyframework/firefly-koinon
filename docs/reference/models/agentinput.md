<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AgentInput

[All wire models](index.md)

Model aliases: `AgentInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `model_options` | [`ModelParameters`](modelparameters.md) or `null` | No | `null` |
| `name` | `string` or `null` | No | `null` |
| `description` | `string` or `null` | No | `null` |
| `provider_id` | `string` or `null` | No | `null` |
| `model_id` | `string` or `null` | No | `null` |
| `tools` | Array of `string` or `null` | No | `null` |
| `scope` | [`KnowledgeScope`](knowledgescope.md) or `null` | No | `null` |
| `instructions` | `string` or `null` | No | `null` |
| `enabled` | `boolean` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### tools

- anyOf branch 1 (Array of `string`): Each item: Allowed values: `"search_knowledge"`, `"inspect_schema"`, `"query_dataset"`, `"propose_catalog_update"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
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
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Name"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Description"
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
        "tools": {
          "anyOf": [
            {
              "items": {
                "enum": [
                  "search_knowledge",
                  "inspect_schema",
                  "query_dataset",
                  "propose_catalog_update"
                ],
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Tools"
        },
        "scope": {
          "anyOf": [
            {
              "$ref": "#/$defs/KnowledgeScope"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "instructions": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Instructions"
        },
        "enabled": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Enabled"
        }
      },
      "title": "AgentInput",
      "type": "object"
    }
    ```
