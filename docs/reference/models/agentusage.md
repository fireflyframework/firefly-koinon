<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AgentUsage

[All wire models](index.md)

Model aliases: `AgentUsage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `agent` | `string` | Yes | Not specified |
| `model` | `string` or `null` | No | `null` |
| `input_tokens` | `integer` | No | `0` |
| `output_tokens` | `integer` | No | `0` |
| `total_tokens` | `integer` | No | `0` |
| `cost_usd` | `number` | No | `0` |
| `latency_ms` | `number` | No | `0` |
| `calls` | `integer` | No | `0` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "agent": {
          "title": "Agent",
          "type": "string"
        },
        "model": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Model"
        },
        "input_tokens": {
          "default": 0,
          "title": "Input Tokens",
          "type": "integer"
        },
        "output_tokens": {
          "default": 0,
          "title": "Output Tokens",
          "type": "integer"
        },
        "total_tokens": {
          "default": 0,
          "title": "Total Tokens",
          "type": "integer"
        },
        "cost_usd": {
          "default": 0,
          "title": "Cost Usd",
          "type": "number"
        },
        "latency_ms": {
          "default": 0,
          "title": "Latency Ms",
          "type": "number"
        },
        "calls": {
          "default": 0,
          "title": "Calls",
          "type": "integer"
        }
      },
      "required": [
        "agent"
      ],
      "title": "AgentUsage",
      "type": "object"
    }
    ```
