<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProcessingResponse

[All wire models](index.md)

Model aliases: `ProcessingResponse`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `observed_at` | `string` | Yes | Not specified |
| `items` | Array of [`ProcessingActivity`](processingactivity.md) | Yes | Not specified |
| `next_page` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### observed_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "observed_at": {
          "format": "date-time",
          "title": "Observed At",
          "type": "string"
        },
        "items": {
          "items": {
            "$ref": "#/$defs/ProcessingActivity"
          },
          "title": "Items",
          "type": "array"
        },
        "next_page": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Next Page"
        }
      },
      "required": [
        "observed_at",
        "items"
      ],
      "title": "ProcessingResponse",
      "type": "object"
    }
    ```
