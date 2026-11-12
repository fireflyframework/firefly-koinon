<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ShareBrowseInput

[All wire models](index.md)

Model aliases: `ShareBrowseInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `q` | `string` | No | `""` |
| `status` | `string` | No | `"all"` |
| `page_size` | `integer` | No | `25` |
| `cursor` | `string` or `null` | No | `null` |
| `reader_source_connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### q

- Maximum length: `512`

### status

- Allowed values: `"all"`, `"active"`, `"revoked"`, `"expired"`

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
        "q": {
          "default": "",
          "maxLength": 512,
          "title": "Q",
          "type": "string"
        },
        "status": {
          "default": "all",
          "enum": [
            "all",
            "active",
            "revoked",
            "expired"
          ],
          "title": "Status",
          "type": "string"
        },
        "page_size": {
          "default": 25,
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
      "title": "ShareBrowseInput",
      "type": "object"
    }
    ```
