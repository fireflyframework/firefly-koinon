<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NativeIndexPage

[All wire models](index.md)

Model aliases: `NativeIndexPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`NativeIndexChoice`](nativeindexchoice.md) | Yes | Not specified |
| `total` | `integer` | Yes | Not specified |
| `limit` | `integer` | Yes | Not specified |
| `offset` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "items": {
          "items": {
            "$ref": "#/$defs/NativeIndexChoice"
          },
          "title": "Items",
          "type": "array"
        },
        "total": {
          "title": "Total",
          "type": "integer"
        },
        "limit": {
          "title": "Limit",
          "type": "integer"
        },
        "offset": {
          "title": "Offset",
          "type": "integer"
        }
      },
      "required": [
        "items",
        "total",
        "limit",
        "offset"
      ],
      "title": "NativeIndexPage",
      "type": "object"
    }
    ```
