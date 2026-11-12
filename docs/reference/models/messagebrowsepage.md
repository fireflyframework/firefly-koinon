<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MessageBrowsePage

[All wire models](index.md)

Model aliases: `MessageBrowsePage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of Map of string keys to [`JsonValue`](jsonvalue.md) | Yes | Not specified |
| `next_cursor` | `string` or `null` | No | `null` |
| `total` | `null` | No | `null` |
| `total_is_exact` | `boolean` | No | `false` |

## Model constraints

- Additional properties: permitted

## Field constraints

### items

- Each item: Additional properties: [`JsonValue`](jsonvalue.md)

### total_is_exact

- Exact value: `false`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "items": {
          "items": {
            "additionalProperties": {
              "$ref": "#/$defs/JsonValue"
            },
            "type": "object"
          },
          "title": "Items",
          "type": "array"
        },
        "next_cursor": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Next Cursor"
        },
        "total": {
          "default": null,
          "title": "Total",
          "type": "null"
        },
        "total_is_exact": {
          "const": false,
          "default": false,
          "title": "Total Is Exact",
          "type": "boolean"
        }
      },
      "required": [
        "items"
      ],
      "title": "MessageBrowsePage",
      "type": "object"
    }
    ```
