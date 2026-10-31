<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeProvider

[All wire models](index.md)

Model aliases: `KnowledgeProvider`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `api` | `string` or `null` | No | `null` |
| `model_ids` | Array of `string` | Yes | Not specified |
| `enabled` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"ollama"`, `"openai"`, `"anthropic"`

### api

- anyOf branch 1 (`string`): Allowed values: `"chat"`, `"responses"`, `"messages"`


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
            "ollama",
            "openai",
            "anthropic"
          ],
          "title": "Kind",
          "type": "string"
        },
        "api": {
          "anyOf": [
            {
              "enum": [
                "chat",
                "responses",
                "messages"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Api"
        },
        "model_ids": {
          "items": {
            "type": "string"
          },
          "title": "Model Ids",
          "type": "array"
        },
        "enabled": {
          "title": "Enabled",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "name",
        "kind",
        "model_ids",
        "enabled"
      ],
      "title": "KnowledgeProvider",
      "type": "object"
    }
    ```
