<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProviderInput

[All wire models](index.md)

Model aliases: `ProviderInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `api` | `string` or `null` | No | `null` |
| `name` | `string` or `null` | No | `null` |
| `kind` | `string` or `null` | No | `null` |
| `base_url` | `string` or `null` | No | `null` |
| `model_ids` | Array of `string` or `null` | No | `null` |
| `secret` | `string` or `null` | No | `null` |
| `enabled` | `boolean` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### api

- anyOf branch 1 (`string`): Allowed values: `"chat"`, `"responses"`, `"messages"`

### kind

- anyOf branch 1 (`string`): Allowed values: `"ollama"`, `"openai"`, `"anthropic"`

### secret

- anyOf branch 1 (`string`): Format: `"password"`
- anyOf branch 1 (`string`): Write only: `true`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
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
        "kind": {
          "anyOf": [
            {
              "enum": [
                "ollama",
                "openai",
                "anthropic"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Kind"
        },
        "base_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Base Url"
        },
        "model_ids": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Model Ids"
        },
        "secret": {
          "anyOf": [
            {
              "format": "password",
              "type": "string",
              "writeOnly": true
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Secret"
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
      "title": "ProviderInput",
      "type": "object"
    }
    ```
