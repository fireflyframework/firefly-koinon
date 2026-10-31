<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeItemPage

[All wire models](index.md)

Model aliases: `KnowledgeItemPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`KnowledgeItemSummary`](knowledgeitemsummary.md) | Yes | Not specified |
| `total` | `integer` | Yes | Not specified |
| `page` | `integer` | Yes | Not specified |
| `page_size` | `integer` | Yes | Not specified |
| `pages` | `integer` | Yes | Not specified |
| `has_next` | `boolean` | Yes | Not specified |
| `has_previous` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### items

- Maximum items: `100`

### total

- Minimum: `0`

### page

- Minimum: `1`

### page_size

- Minimum: `1`
- Maximum: `100`

### pages

- Minimum: `0`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "items": {
          "items": {
            "$ref": "#/$defs/KnowledgeItemSummary"
          },
          "maxItems": 100,
          "title": "Items",
          "type": "array"
        },
        "total": {
          "minimum": 0,
          "title": "Total",
          "type": "integer"
        },
        "page": {
          "minimum": 1,
          "title": "Page",
          "type": "integer"
        },
        "page_size": {
          "maximum": 100,
          "minimum": 1,
          "title": "Page Size",
          "type": "integer"
        },
        "pages": {
          "minimum": 0,
          "title": "Pages",
          "type": "integer"
        },
        "has_next": {
          "title": "Has Next",
          "type": "boolean"
        },
        "has_previous": {
          "title": "Has Previous",
          "type": "boolean"
        }
      },
      "required": [
        "items",
        "total",
        "page",
        "page_size",
        "pages",
        "has_next",
        "has_previous"
      ],
      "title": "KnowledgeItemPage",
      "type": "object"
    }
    ```
