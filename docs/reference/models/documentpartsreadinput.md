<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentPartsReadInput

[All wire models](index.md)

Model aliases: `DocumentPartsReadInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `reader_source_connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) or `null` | No | `null` |
| `page` | `integer` | No | `1` |
| `page_size` | `integer` | No | `25` |
| `kind` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### reader_source_connections

- anyOf branch 1 (Array of [`ReaderSourceSelection`](readersourceselection.md)): Maximum items: `100`

### page

- Minimum: `1`
- Maximum: `100000`

### page_size

- Minimum: `1`
- Maximum: `100`

### kind

- anyOf branch 1 (`string`): Allowed values: `"artifact"`, `"section"`, `"chunk"`, `"page"`


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
        "page": {
          "default": 1,
          "maximum": 100000,
          "minimum": 1,
          "title": "Page",
          "type": "integer"
        },
        "page_size": {
          "default": 25,
          "maximum": 100,
          "minimum": 1,
          "title": "Page Size",
          "type": "integer"
        },
        "kind": {
          "anyOf": [
            {
              "enum": [
                "artifact",
                "section",
                "chunk",
                "page"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Kind"
        }
      },
      "title": "DocumentPartsReadInput",
      "type": "object"
    }
    ```
