<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GlossaryPage

[All wire models](index.md)

Model aliases: `GlossaryPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`GlossaryTermRead`](glossarytermread.md) | Yes | Not specified |
| `total` | `integer` or `null` | No | `null` |
| `limit` | `integer` or `null` | No | `null` |
| `offset` | `integer` or `null` | No | `null` |
| `has_more` | `boolean` or `null` | No | `null` |

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
            "$ref": "#/$defs/GlossaryTermRead"
          },
          "title": "Items",
          "type": "array"
        },
        "total": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Total"
        },
        "limit": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Limit"
        },
        "offset": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Offset"
        },
        "has_more": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Has More"
        }
      },
      "required": [
        "items"
      ],
      "title": "GlossaryPage",
      "type": "object"
    }
    ```
