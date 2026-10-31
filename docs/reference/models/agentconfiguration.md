<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AgentConfiguration

[All wire models](index.md)

Model aliases: `AgentConfiguration`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `model_settings` | Map of string keys to [`JsonValue`](jsonvalue.md) | No | Not specified |
| `input_modalities` | Array of `string` | No | Not specified |
| `input_modality_policy` | `string` or `null` | No | `null` |
| `model_options_supported` | Array of `string` | No | Not specified |
| `api` | `string` or `null` | No | `null` |
| `model_class` | `string` or `null` | No | `null` |
| `model_options` | [`ModelParameters`](modelparameters.md) | No | Not specified |
| `configured` | `boolean` | No | `false` |
| `can_run` | `boolean` | No | `false` |
| `dependencies` | Array of [`ModelConnection`](modelconnection.md) | No | Not specified |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `description` | `string` | Yes | Not specified |
| `provider_id` | `string` | Yes | Not specified |
| `model_id` | `string` | Yes | Not specified |
| `tools` | Array of `string` | Yes | Not specified |
| `scope` | [`KnowledgeScope`](knowledgescope.md) | Yes | Not specified |
| `instructions` | `string` | Yes | Not specified |
| `enabled` | `boolean` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `checks` | Array of [`SetupCheck`](setupcheck.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### model_settings

- Additional properties: [`JsonValue`](jsonvalue.md)

### input_modalities

- Each item: Allowed values: `"text"`, `"image"`, `"audio"`

### api

- anyOf branch 1 (`string`): Allowed values: `"chat"`, `"responses"`, `"messages"`

### model_class

- anyOf branch 1 (`string`): Allowed values: `"OpenAIChatModel"`, `"OpenAIResponsesModel"`, `"AnthropicModel"`

### tools

- Each item: Allowed values: `"search_knowledge"`, `"inspect_schema"`, `"query_dataset"`, `"propose_catalog_update"`

### status

- Allowed values: `"ready"`, `"needs_setup"`, `"unverified"`, `"disabled"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "model_settings": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Model Settings",
          "type": "object"
        },
        "input_modalities": {
          "items": {
            "enum": [
              "text",
              "image",
              "audio"
            ],
            "type": "string"
          },
          "title": "Input Modalities",
          "type": "array"
        },
        "input_modality_policy": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Input Modality Policy"
        },
        "model_options_supported": {
          "items": {
            "type": "string"
          },
          "title": "Model Options Supported",
          "type": "array"
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
        "model_class": {
          "anyOf": [
            {
              "enum": [
                "OpenAIChatModel",
                "OpenAIResponsesModel",
                "AnthropicModel"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Model Class"
        },
        "model_options": {
          "$ref": "#/$defs/ModelParameters"
        },
        "configured": {
          "default": false,
          "title": "Configured",
          "type": "boolean"
        },
        "can_run": {
          "default": false,
          "title": "Can Run",
          "type": "boolean"
        },
        "dependencies": {
          "items": {
            "$ref": "#/$defs/ModelConnection"
          },
          "title": "Dependencies",
          "type": "array"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "description": {
          "title": "Description",
          "type": "string"
        },
        "provider_id": {
          "title": "Provider Id",
          "type": "string"
        },
        "model_id": {
          "title": "Model Id",
          "type": "string"
        },
        "tools": {
          "items": {
            "enum": [
              "search_knowledge",
              "inspect_schema",
              "query_dataset",
              "propose_catalog_update"
            ],
            "type": "string"
          },
          "title": "Tools",
          "type": "array"
        },
        "scope": {
          "$ref": "#/$defs/KnowledgeScope"
        },
        "instructions": {
          "title": "Instructions",
          "type": "string"
        },
        "enabled": {
          "title": "Enabled",
          "type": "boolean"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "status": {
          "enum": [
            "ready",
            "needs_setup",
            "unverified",
            "disabled"
          ],
          "title": "Status",
          "type": "string"
        },
        "checks": {
          "items": {
            "$ref": "#/$defs/SetupCheck"
          },
          "title": "Checks",
          "type": "array"
        }
      },
      "required": [
        "id",
        "name",
        "description",
        "provider_id",
        "model_id",
        "tools",
        "scope",
        "instructions",
        "enabled",
        "revision",
        "status",
        "checks"
      ],
      "title": "AgentConfiguration",
      "type": "object"
    }
    ```
