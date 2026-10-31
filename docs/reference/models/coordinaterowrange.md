<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CoordinateRowRange

[All wire models](index.md)

Model aliases: `CoordinateRowRange`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `output_start` | `integer` | Yes | Not specified |
| `count` | `integer` | Yes | Not specified |
| `source_start` | `integer` | Yes | Not specified |
| `source_stride` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### output_start

- Minimum: `0`
- Maximum: `9007199254740991`

### count

- Minimum: `1`
- Maximum: `9007199254740991`

### source_start

- Minimum: `0`
- Maximum: `9007199254740991`

### source_stride

- Minimum: `1`
- Maximum: `9007199254740991`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "output_start": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Output Start",
          "type": "integer"
        },
        "count": {
          "maximum": 9007199254740991,
          "minimum": 1,
          "title": "Count",
          "type": "integer"
        },
        "source_start": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Source Start",
          "type": "integer"
        },
        "source_stride": {
          "maximum": 9007199254740991,
          "minimum": 1,
          "title": "Source Stride",
          "type": "integer"
        }
      },
      "required": [
        "output_start",
        "count",
        "source_start",
        "source_stride"
      ],
      "title": "CoordinateRowRange",
      "type": "object"
    }
    ```
