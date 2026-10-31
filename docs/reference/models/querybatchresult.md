<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryBatchResult

[All wire models](index.md)

Model aliases: `QueryBatchResult`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `batch_id` | `string` | Yes | Not specified |
| `item_id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `result` | [`BatchQueryOutcome`](batchqueryoutcome.md) or `null` | No | `null` |
| `error_code` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"queued"`, `"running"`, `"succeeded"`, `"failed"`, `"cancelled"`, `"reconciling"`


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
        "item_id": {
          "title": "Item Id",
          "type": "string"
        },
        "status": {
          "enum": [
            "queued",
            "running",
            "succeeded",
            "failed",
            "cancelled",
            "reconciling"
          ],
          "title": "Status",
          "type": "string"
        },
        "result": {
          "anyOf": [
            {
              "$ref": "#/$defs/BatchQueryOutcome"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Code"
        }
      },
      "required": [
        "batch_id",
        "item_id",
        "status"
      ],
      "title": "QueryBatchResult",
      "type": "object"
    }
    ```
