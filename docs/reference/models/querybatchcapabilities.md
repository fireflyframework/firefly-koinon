<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryBatchCapabilities

[All wire models](index.md)

Model aliases: `QueryBatchCapabilities`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `configured` | `boolean` | Yes | Not specified |
| `processing_policy` | `string` | No | `"independent_nl_v1"` |
| `automatic_unknown_replay` | `boolean` | No | `false` |
| `shared_conversation` | `boolean` | No | `false` |
| `connection_mode` | `string` | No | `"explicit_provider"` |
| `max_queries` | `integer` | No | `20` |
| `max_question_characters` | `integer` | No | `8000` |
| `max_question_bytes_per_batch` | `integer` | No | `65536` |
| `max_result_bytes` | `integer` | No | `1048576` |

## Model constraints

- Additional properties: permitted

## Field constraints

### processing_policy

- Exact value: `"independent_nl_v1"`

### automatic_unknown_replay

- Exact value: `false`

### shared_conversation

- Exact value: `false`

### connection_mode

- Exact value: `"explicit_provider"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "configured": {
          "title": "Configured",
          "type": "boolean"
        },
        "processing_policy": {
          "const": "independent_nl_v1",
          "default": "independent_nl_v1",
          "title": "Processing Policy",
          "type": "string"
        },
        "automatic_unknown_replay": {
          "const": false,
          "default": false,
          "title": "Automatic Unknown Replay",
          "type": "boolean"
        },
        "shared_conversation": {
          "const": false,
          "default": false,
          "title": "Shared Conversation",
          "type": "boolean"
        },
        "connection_mode": {
          "const": "explicit_provider",
          "default": "explicit_provider",
          "title": "Connection Mode",
          "type": "string"
        },
        "max_queries": {
          "default": 20,
          "title": "Max Queries",
          "type": "integer"
        },
        "max_question_characters": {
          "default": 8000,
          "title": "Max Question Characters",
          "type": "integer"
        },
        "max_question_bytes_per_batch": {
          "default": 65536,
          "title": "Max Question Bytes Per Batch",
          "type": "integer"
        },
        "max_result_bytes": {
          "default": 1048576,
          "title": "Max Result Bytes",
          "type": "integer"
        }
      },
      "required": [
        "configured"
      ],
      "title": "QueryBatchCapabilities",
      "type": "object"
    }
    ```
