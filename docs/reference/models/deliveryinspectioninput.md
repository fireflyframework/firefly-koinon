<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DeliveryInspectionInput

[All wire models](index.md)

Model aliases: `DeliveryInspectionInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_generation` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_generation

- Minimum: `0`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_generation": {
          "minimum": 0,
          "title": "Expected Generation",
          "type": "integer"
        }
      },
      "required": [
        "expected_generation"
      ],
      "title": "DeliveryInspectionInput",
      "type": "object"
    }
    ```
