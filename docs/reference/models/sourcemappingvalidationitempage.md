<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceMappingValidationItemPage

[All wire models](index.md)

Model aliases: `SourceMappingValidationItemPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `validation_id` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `items` | Array of [`SourceMappingValidationItem`](sourcemappingvalidationitem.md) | Yes | Not specified |
| `visible_count` | `integer` | Yes | Not specified |
| `next_cursor` | `string` or `null` | Yes | Not specified |
| `total` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### validation_id

- Format: `"uuid"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "validation_id": {
          "format": "uuid",
          "title": "Validation Id",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "items": {
          "items": {
            "$ref": "#/$defs/SourceMappingValidationItem"
          },
          "title": "Items",
          "type": "array"
        },
        "visible_count": {
          "title": "Visible Count",
          "type": "integer"
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
        }
      },
      "required": [
        "validation_id",
        "revision",
        "items",
        "visible_count",
        "next_cursor"
      ],
      "title": "SourceMappingValidationItemPage",
      "type": "object"
    }
    ```
