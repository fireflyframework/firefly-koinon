<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryBatchItemPage

[All wire models](index.md)

Model aliases: `QueryBatchItemPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`QueryBatchItemView`](querybatchitemview.md) | Yes | Not specified |
| `total` | `integer` | Yes | Not specified |
| `page` | `integer` | Yes | Not specified |
| `page_size` | `integer` | Yes | Not specified |
| `pages` | `integer` | Yes | Not specified |

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
            "$ref": "#/$defs/QueryBatchItemView"
          },
          "title": "Items",
          "type": "array"
        },
        "total": {
          "title": "Total",
          "type": "integer"
        },
        "page": {
          "title": "Page",
          "type": "integer"
        },
        "page_size": {
          "title": "Page Size",
          "type": "integer"
        },
        "pages": {
          "title": "Pages",
          "type": "integer"
        }
      },
      "required": [
        "items",
        "total",
        "page",
        "page_size",
        "pages"
      ],
      "title": "QueryBatchItemPage",
      "type": "object"
    }
    ```
