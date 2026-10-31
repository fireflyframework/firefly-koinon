<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CoordinateCellPosition

[All wire models](index.md)

Model aliases: `CoordinateCellPosition`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `row` | `integer` | Yes | Not specified |
| `column` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### row

- Minimum: `0`
- Maximum: `9007199254740991`

### column

- Minimum: `0`
- Maximum: `9007199254740991`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "row": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Row",
          "type": "integer"
        },
        "column": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Column",
          "type": "integer"
        }
      },
      "required": [
        "row",
        "column"
      ],
      "title": "CoordinateCellPosition",
      "type": "object"
    }
    ```
