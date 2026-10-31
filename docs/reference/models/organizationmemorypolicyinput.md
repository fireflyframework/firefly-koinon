<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationMemoryPolicyInput

[All wire models](index.md)

Model aliases: `OrganizationMemoryPolicyInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `allow_project_memory` | `boolean` | No | `true` |
| `max_history_messages` | `integer` | No | `40` |
| `max_history_tokens` | `integer` | No | `8192` |
| `max_project_memory_messages` | `integer` | No | `20` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### max_history_messages

- Minimum: `0`
- Maximum: `40`

### max_history_tokens

- Minimum: `0`
- Maximum: `65536`

### max_project_memory_messages

- Minimum: `0`
- Maximum: `40`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "allow_project_memory": {
          "default": true,
          "title": "Allow Project Memory",
          "type": "boolean"
        },
        "max_history_messages": {
          "default": 40,
          "maximum": 40,
          "minimum": 0,
          "title": "Max History Messages",
          "type": "integer"
        },
        "max_history_tokens": {
          "default": 8192,
          "maximum": 65536,
          "minimum": 0,
          "title": "Max History Tokens",
          "type": "integer"
        },
        "max_project_memory_messages": {
          "default": 20,
          "maximum": 40,
          "minimum": 0,
          "title": "Max Project Memory Messages",
          "type": "integer"
        }
      },
      "title": "OrganizationMemoryPolicyInput",
      "type": "object"
    }
    ```
