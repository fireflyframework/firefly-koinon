<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ModelProvider

[All wire models](index.md)

Model aliases: `ModelProvider`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `native_adapter` | [`NativeAdapter`](nativeadapter.md) or `null` | No | `null` |
| `api` | `string` or `null` | No | `null` |
| `model_class` | `string` or `null` | No | `null` |
| `configured` | `boolean` | No | `false` |
| `connected` | `boolean` | No | `false` |
| `discovered` | `boolean` | No | `false` |
| `model_capabilities` | Array of [`ModelCapability`](modelcapability.md) | No | Not specified |
| `configuration_ownership` | `string` | No | `"tenant"` |
| `credential_ownership` | `string` | No | `"none"` |
| `ambient_credentials` | `boolean` | No | `false` |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `base_url` | `string` | Yes | Not specified |
| `model_ids` | Array of `string` | Yes | Not specified |
| `enabled` | `boolean` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `secret_configured` | `boolean` | Yes | Not specified |
| `validated` | `boolean` | Yes | Not specified |
| `checks` | Array of [`SetupCheck`](setupcheck.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### api

- anyOf branch 1 (`string`): Allowed values: `"chat"`, `"responses"`, `"messages"`

### model_class

- anyOf branch 1 (`string`): Allowed values: `"OpenAIChatModel"`, `"OpenAIResponsesModel"`, `"AnthropicModel"`

### configuration_ownership

- Exact value: `"tenant"`

### credential_ownership

- Allowed values: `"tenant"`, `"none"`

### ambient_credentials

- Exact value: `false`

### kind

- Allowed values: `"ollama"`, `"openai"`, `"anthropic"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "native_adapter": {
          "anyOf": [
            {
              "$ref": "#/$defs/NativeAdapter"
            },
            {
              "type": "null"
            }
          ],
          "default": null
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
        "configured": {
          "default": false,
          "title": "Configured",
          "type": "boolean"
        },
        "connected": {
          "default": false,
          "title": "Connected",
          "type": "boolean"
        },
        "discovered": {
          "default": false,
          "title": "Discovered",
          "type": "boolean"
        },
        "model_capabilities": {
          "items": {
            "$ref": "#/$defs/ModelCapability"
          },
          "title": "Model Capabilities",
          "type": "array"
        },
        "configuration_ownership": {
          "const": "tenant",
          "default": "tenant",
          "title": "Configuration Ownership",
          "type": "string"
        },
        "credential_ownership": {
          "default": "none",
          "enum": [
            "tenant",
            "none"
          ],
          "title": "Credential Ownership",
          "type": "string"
        },
        "ambient_credentials": {
          "const": false,
          "default": false,
          "title": "Ambient Credentials",
          "type": "boolean"
        },
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
        "base_url": {
          "title": "Base Url",
          "type": "string"
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
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "secret_configured": {
          "title": "Secret Configured",
          "type": "boolean"
        },
        "validated": {
          "title": "Validated",
          "type": "boolean"
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
        "kind",
        "base_url",
        "model_ids",
        "enabled",
        "revision",
        "secret_configured",
        "validated",
        "checks"
      ],
      "title": "ModelProvider",
      "type": "object"
    }
    ```
