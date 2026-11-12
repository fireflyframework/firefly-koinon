<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentChunksReadInput

[All wire models](index.md)

Model aliases: `DocumentChunksReadInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `reader_source_connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) or `null` | No | `null` |
| `offset` | `integer` | No | `0` |
| `limit` | `integer` | No | `50` |
| `page` | `integer` or `null` | No | `null` |
| `section` | `string` or `null` | No | `null` |
| `q` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### reader_source_connections

- anyOf branch 1 (Array of [`ReaderSourceSelection`](readersourceselection.md)): Maximum items: `100`

### offset

- Minimum: `0`

### limit

- Minimum: `1`
- Maximum: `100`

### page

- anyOf branch 1 (`integer`): Minimum: `1`

### section

- anyOf branch 1 (`string`): Maximum length: `512`

### q

- anyOf branch 1 (`string`): Maximum length: `255`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "reader_source_connections": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/ReaderSourceSelection"
              },
              "maxItems": 100,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reader Source Connections"
        },
        "offset": {
          "default": 0,
          "minimum": 0,
          "title": "Offset",
          "type": "integer"
        },
        "limit": {
          "default": 50,
          "maximum": 100,
          "minimum": 1,
          "title": "Limit",
          "type": "integer"
        },
        "page": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page"
        },
        "section": {
          "anyOf": [
            {
              "maxLength": 512,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Section"
        },
        "q": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Q"
        }
      },
      "title": "DocumentChunksReadInput",
      "type": "object"
    }
    ```
