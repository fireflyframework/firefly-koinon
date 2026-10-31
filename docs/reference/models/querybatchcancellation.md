<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryBatchCancellation

[All wire models](index.md)

Model aliases: `QueryBatchCancellation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `batch_id` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `cancellation_requested` | `boolean` | No | `true` |

## Model constraints

- Additional properties: permitted

## Field constraints

### revision

- Minimum: `1`
- Maximum: `2147483647`

### cancellation_requested

- Exact value: `true`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "batch_id": {
          "title": "Batch Id",
          "type": "string"
        },
        "revision": {
          "maximum": 2147483647,
          "minimum": 1,
          "title": "Revision",
          "type": "integer"
        },
        "cancellation_requested": {
          "const": true,
          "default": true,
          "title": "Cancellation Requested",
          "type": "boolean"
        }
      },
      "required": [
        "batch_id",
        "revision"
      ],
      "title": "QueryBatchCancellation",
      "type": "object"
    }
    ```
