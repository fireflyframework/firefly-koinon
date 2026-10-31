<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Page_PersonalToken_

[All wire models](index.md)

Model aliases: `Page[PersonalToken]`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `summaries` | Map of string keys to [`CatalogSummary`](catalogsummary.md) | No | Not specified |
| `page` | `integer` or `null` | No | `null` |
| `size` | `integer` or `null` | No | `null` |
| `page_size` | `integer` or `null` | No | `null` |
| `pages` | `integer` or `null` | No | `null` |
| `next_cursor` | `string` or `null` | No | `null` |
| `actors` | Map of string keys to [`AuthorSummary`](authorsummary.md) | No | Not specified |
| `items` | Array of [`PersonalToken`](personaltoken.md) | Yes | Not specified |
| `total` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### summaries

- Additional properties: [`CatalogSummary`](catalogsummary.md)

### actors

- Additional properties: [`AuthorSummary`](authorsummary.md)


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "summaries": {
          "additionalProperties": {
            "$ref": "#/$defs/CatalogSummary"
          },
          "title": "Summaries",
          "type": "object"
        },
        "page": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page"
        },
        "size": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Size"
        },
        "page_size": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page Size"
        },
        "pages": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Pages"
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
        "actors": {
          "additionalProperties": {
            "$ref": "#/$defs/AuthorSummary"
          },
          "title": "Actors",
          "type": "object"
        },
        "items": {
          "items": {
            "$ref": "#/$defs/PersonalToken"
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
        }
      },
      "required": [
        "items"
      ],
      "title": "Page[PersonalToken]",
      "type": "object"
    }
    ```
