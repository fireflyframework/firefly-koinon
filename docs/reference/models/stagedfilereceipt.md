<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# StagedFileReceipt

[All wire models](index.md)

Model aliases: `StagedFileReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `receipt_id` | `string` | Yes | Not specified |
| `batch_id` | `string` | Yes | Not specified |
| `item_id` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `size_bytes` | `integer` | Yes | Not specified |
| `status` | `string` | No | `"staged"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Exact value: `"staged"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "receipt_id": {
          "title": "Receipt Id",
          "type": "string"
        },
        "batch_id": {
          "title": "Batch Id",
          "type": "string"
        },
        "item_id": {
          "title": "Item Id",
          "type": "string"
        },
        "sha256": {
          "title": "Sha256",
          "type": "string"
        },
        "size_bytes": {
          "title": "Size Bytes",
          "type": "integer"
        },
        "status": {
          "const": "staged",
          "default": "staged",
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "receipt_id",
        "batch_id",
        "item_id",
        "sha256",
        "size_bytes"
      ],
      "title": "StagedFileReceipt",
      "type": "object"
    }
    ```
