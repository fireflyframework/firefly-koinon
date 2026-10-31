<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# UsageSummary

[All wire models](index.md)

Model aliases: `UsageSummary`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `total_input_tokens` | `integer` | No | `0` |
| `total_output_tokens` | `integer` | No | `0` |
| `total_tokens` | `integer` | No | `0` |
| `total_cost_usd` | `number` | No | `0` |
| `total_latency_ms` | `number` | No | `0` |
| `by_agent` | Array of [`AgentUsage`](agentusage.md) | No | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "total_input_tokens": {
          "default": 0,
          "title": "Total Input Tokens",
          "type": "integer"
        },
        "total_output_tokens": {
          "default": 0,
          "title": "Total Output Tokens",
          "type": "integer"
        },
        "total_tokens": {
          "default": 0,
          "title": "Total Tokens",
          "type": "integer"
        },
        "total_cost_usd": {
          "default": 0,
          "title": "Total Cost Usd",
          "type": "number"
        },
        "total_latency_ms": {
          "default": 0,
          "title": "Total Latency Ms",
          "type": "number"
        },
        "by_agent": {
          "items": {
            "$ref": "#/$defs/AgentUsage"
          },
          "title": "By Agent",
          "type": "array"
        }
      },
      "title": "UsageSummary",
      "type": "object"
    }
    ```
