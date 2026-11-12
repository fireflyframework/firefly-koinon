<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MessageBrowseInput

[All wire models](index.md)

Model aliases: `MessageBrowseInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `page_size` | `integer` | No | `50` |
| `cursor` | `string` or `null` | No | `null` |
| `reader_source_connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### page_size

- Minimum: `1`
- Maximum: `100`

### cursor

- anyOf branch 1 (`string`): Maximum length: `128`

### reader_source_connections

- anyOf branch 1 (Array of [`ReaderSourceSelection`](readersourceselection.md)): Maximum items: `100`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "page_size": {
          "default": 50,
          "maximum": 100,
          "minimum": 1,
          "title": "Page Size",
          "type": "integer"
        },
        "cursor": {
          "anyOf": [
            {
              "maxLength": 128,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Cursor"
        },
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
        }
      },
      "title": "MessageBrowseInput",
      "type": "object"
    }
    ```
