<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CoordinateSourceCell

[All wire models](index.md)

Model aliases: `CoordinateSourceCell`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `output_row` | `integer` | Yes | Not specified |
| `output_column` | `integer` | Yes | Not specified |
| `source_row` | `integer` or `null` | Yes | Not specified |
| `source_column` | `integer` or `null` | Yes | Not specified |
| `source_path` | Array of `string` or `integer` | Yes | Not specified |
| `header_cells` | Array of [`CoordinateHeaderCell`](coordinateheadercell.md) | Yes | Not specified |
| `source_type` | `string` or `null` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### output_row

- Minimum: `0`
- Maximum: `9007199254740991`

### output_column

- Minimum: `0`
- Maximum: `9007199254740991`

### source_row

- anyOf branch 1 (`integer`): Minimum: `0`
- anyOf branch 1 (`integer`): Maximum: `9007199254740991`

### source_column

- anyOf branch 1 (`integer`): Minimum: `0`
- anyOf branch 1 (`integer`): Maximum: `9007199254740991`

### source_path

- Maximum items: `64`
- Each item: anyOf branch 1 (`string`): Maximum length: `4096`
- Each item: anyOf branch 2 (`integer`): Minimum: `0`
- Each item: anyOf branch 2 (`integer`): Maximum: `9007199254740991`

### header_cells

- Maximum items: `1024`

### source_type

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `4096`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "output_row": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Output Row",
          "type": "integer"
        },
        "output_column": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Output Column",
          "type": "integer"
        },
        "source_row": {
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
          "title": "Source Row"
        },
        "source_column": {
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
          "title": "Source Column"
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
        "header_cells": {
          "items": {
            "$ref": "#/$defs/CoordinateHeaderCell"
          },
          "maxItems": 1024,
          "title": "Header Cells",
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
        }
      },
      "required": [
        "output_row",
        "output_column",
        "source_row",
        "source_column",
        "source_path",
        "header_cells",
        "source_type"
      ],
      "title": "CoordinateSourceCell",
      "type": "object"
    }
    ```
