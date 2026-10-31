<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ModelParameters

[All wire models](index.md)

Model aliases: `ModelParameters`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `output_mode` | `string` or `null` | No | `null` |
| `max_tokens` | `integer` | No | `4096` |
| `temperature` | `number` or `null` | No | `null` |
| `top_p` | `number` or `null` | No | `null` |
| `top_k` | `integer` or `null` | No | `null` |
| `seed` | `integer` or `null` | No | `null` |
| `stop_sequences` | Array of `string` or `null` | No | `null` |
| `request_timeout` | `number` or `null` | No | `null` |
| `reasoning` | `string` or `null` | No | `null` |
| `reasoning_budget_tokens` | `integer` or `null` | No | `null` |
| `parallel_tool_calls` | `boolean` or `null` | No | `null` |
| `store_responses` | `boolean` or `null` | No | `null` |
| `output_verbosity` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### output_mode

- anyOf branch 1 (`string`): Allowed values: `"default"`, `"native"`

### max_tokens

- Minimum: `64`
- Maximum: `16384`

### temperature

- anyOf branch 1 (`number`): Minimum: `0`
- anyOf branch 1 (`number`): Maximum: `2`

### top_p

- anyOf branch 1 (`number`): Minimum: `0`
- anyOf branch 1 (`number`): Maximum: `1`

### top_k

- anyOf branch 1 (`integer`): Minimum: `1`
- anyOf branch 1 (`integer`): Maximum: `1000`

### seed

- anyOf branch 1 (`integer`): Minimum: `-2147483648`
- anyOf branch 1 (`integer`): Maximum: `2147483647`

### stop_sequences

- anyOf branch 1 (Array of `string`): Maximum items: `8`
- anyOf branch 1 (Array of `string`): Each item: Minimum length: `1`
- anyOf branch 1 (Array of `string`): Each item: Maximum length: `256`

### request_timeout

- anyOf branch 1 (`number`): Minimum: `0.1`
- anyOf branch 1 (`number`): Maximum: `120`

### reasoning

- anyOf branch 1 (`string`): Allowed values: `"none"`, `"minimal"`, `"low"`, `"medium"`, `"high"`, `"xhigh"`

### reasoning_budget_tokens

- anyOf branch 1 (`integer`): Minimum: `1024`
- anyOf branch 1 (`integer`): Maximum: `16000`

### output_verbosity

- anyOf branch 1 (`string`): Allowed values: `"low"`, `"medium"`, `"high"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "output_mode": {
          "anyOf": [
            {
              "enum": [
                "default",
                "native"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Output Mode"
        },
        "max_tokens": {
          "default": 4096,
          "maximum": 16384,
          "minimum": 64,
          "title": "Max Tokens",
          "type": "integer"
        },
        "temperature": {
          "anyOf": [
            {
              "maximum": 2,
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Temperature"
        },
        "top_p": {
          "anyOf": [
            {
              "maximum": 1,
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Top P"
        },
        "top_k": {
          "anyOf": [
            {
              "maximum": 1000,
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Top K"
        },
        "seed": {
          "anyOf": [
            {
              "maximum": 2147483647,
              "minimum": -2147483648,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Seed"
        },
        "stop_sequences": {
          "anyOf": [
            {
              "items": {
                "maxLength": 256,
                "minLength": 1,
                "type": "string"
              },
              "maxItems": 8,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stop Sequences"
        },
        "request_timeout": {
          "anyOf": [
            {
              "maximum": 120,
              "minimum": 0.1,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Request Timeout"
        },
        "reasoning": {
          "anyOf": [
            {
              "enum": [
                "none",
                "minimal",
                "low",
                "medium",
                "high",
                "xhigh"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reasoning"
        },
        "reasoning_budget_tokens": {
          "anyOf": [
            {
              "maximum": 16000,
              "minimum": 1024,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reasoning Budget Tokens"
        },
        "parallel_tool_calls": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parallel Tool Calls"
        },
        "store_responses": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Store Responses"
        },
        "output_verbosity": {
          "anyOf": [
            {
              "enum": [
                "low",
                "medium",
                "high"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Output Verbosity"
        }
      },
      "title": "ModelParameters",
      "type": "object"
    }
    ```
