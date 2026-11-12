<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ReaderSelectionInput

[All wire models](index.md)

Model aliases: `ReaderSelectionInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `operation_id` | `string` | Yes | Not specified |
| `connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `0`

### operation_id

- Format: `"uuid"`

### connections

- Maximum items: `100`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "minimum": 0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "operation_id": {
          "format": "uuid",
          "title": "Operation Id",
          "type": "string"
        },
        "connections": {
          "items": {
            "$ref": "#/$defs/ReaderSourceSelection"
          },
          "maxItems": 100,
          "title": "Connections",
          "type": "array"
        }
      },
      "required": [
        "expected_revision",
        "operation_id",
        "connections"
      ],
      "title": "ReaderSelectionInput",
      "type": "object"
    }
    ```
