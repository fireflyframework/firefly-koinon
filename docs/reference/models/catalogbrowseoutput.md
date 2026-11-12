<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CatalogBrowseOutput

[All wire models](index.md)

Model aliases: `CatalogBrowseOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`CatalogEntry`](catalogentry.md) | Yes | Not specified |
| `actors` | Map of string keys to [`AuthorSummary`](authorsummary.md) | Yes | Not specified |
| `next_cursor` | `string` or `null` | Yes | Not specified |
| `summaries` | Map of string keys to [`CatalogSummary`](catalogsummary.md) | No | Not specified |
| `total` | `null` | No | `null` |
| `total_is_exact` | `boolean` | No | `false` |

## Model constraints

- Additional properties: permitted

## Field constraints

### actors

- Additional properties: [`AuthorSummary`](authorsummary.md)

### summaries

- Additional properties: [`CatalogSummary`](catalogsummary.md)

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
            "$ref": "#/$defs/CatalogEntry"
          },
          "title": "Items",
          "type": "array"
        },
        "actors": {
          "additionalProperties": {
            "$ref": "#/$defs/AuthorSummary"
          },
          "title": "Actors",
          "type": "object"
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
        "summaries": {
          "additionalProperties": {
            "$ref": "#/$defs/CatalogSummary"
          },
          "title": "Summaries",
          "type": "object"
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
        "items",
        "actors",
        "next_cursor"
      ],
      "title": "CatalogBrowseOutput",
      "type": "object"
    }
    ```
