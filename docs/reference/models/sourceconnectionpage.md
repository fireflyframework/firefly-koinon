<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceConnectionPage

[All wire models](index.md)

Model aliases: `SourceConnectionPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`SourceConnectionOutput`](sourceconnectionoutput.md) | Yes | Not specified |
| `next_cursor` | `string` or `null` | Yes | Not specified |
| `synchronization_available` | `boolean` | No | `false` |

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
            "$ref": "#/$defs/SourceConnectionOutput"
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
          "title": "Next Cursor"
        },
        "synchronization_available": {
          "default": false,
          "title": "Synchronization Available",
          "type": "boolean"
        }
      },
      "required": [
        "items",
        "next_cursor"
      ],
      "title": "SourceConnectionPage",
      "type": "object"
    }
    ```
