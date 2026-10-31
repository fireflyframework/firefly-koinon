<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CoordinateColumnBinding

[All wire models](index.md)

Model aliases: `CoordinateColumnBinding`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `output_position` | `integer` | Yes | Not specified |
| `source_field_index` | `integer` or `null` | Yes | Not specified |
| `source_path` | Array of `string` or `integer` | Yes | Not specified |
| `source_type` | `string` or `null` | Yes | Not specified |
| `header_cells` | Array of [`CoordinateHeaderCell`](coordinateheadercell.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### output_position

- Minimum: `0`
- Maximum: `9007199254740991`

### source_field_index

- anyOf branch 1 (`integer`): Minimum: `0`
- anyOf branch 1 (`integer`): Maximum: `9007199254740991`

### source_path

- Maximum items: `64`
- Each item: anyOf branch 1 (`string`): Maximum length: `4096`
- Each item: anyOf branch 2 (`integer`): Minimum: `0`
- Each item: anyOf branch 2 (`integer`): Maximum: `9007199254740991`

### source_type

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `4096`

### header_cells

- Maximum items: `1024`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "output_position": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Output Position",
          "type": "integer"
        },
        "source_field_index": {
          "anyOf": [
            {
              "maximum": 9007199254740991,
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Source Field Index"
        },
        "source_path": {
          "items": {
            "anyOf": [
              {
                "maxLength": 4096,
                "type": "string"
              },
              {
                "maximum": 9007199254740991,
                "minimum": 0,
                "type": "integer"
              }
            ]
          },
          "maxItems": 64,
          "title": "Source Path",
          "type": "array"
        },
        "source_type": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Source Type"
        },
        "header_cells": {
          "items": {
            "$ref": "#/$defs/CoordinateHeaderCell"
          },
          "maxItems": 1024,
          "title": "Header Cells",
          "type": "array"
        }
      },
      "required": [
        "output_position",
        "source_field_index",
        "source_path",
        "source_type",
        "header_cells"
      ],
      "title": "CoordinateColumnBinding",
      "type": "object"
    }
    ```
