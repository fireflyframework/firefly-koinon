<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ActivityCoverage

[All wire models](index.md)

Model aliases: `ActivityCoverage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `observed_since` | `string` or `null` | Yes | Not specified |
| `complete_window` | `boolean` | Yes | Not specified |
| `missing_observations` | `integer` or `null` | No | `null` |
| `reasons` | Array of `string` | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### observed_since

- anyOf branch 1 (`string`): Format: `"date-time"`

### missing_observations

- anyOf branch 1 (`integer`): Minimum: `0`

### reasons

- Maximum items: `10`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "observed_since": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Observed Since"
        },
        "complete_window": {
          "title": "Complete Window",
          "type": "boolean"
        },
        "missing_observations": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Missing Observations"
        },
        "reasons": {
          "items": {
            "type": "string"
          },
          "maxItems": 10,
          "title": "Reasons",
          "type": "array"
        }
      },
      "required": [
        "observed_since",
        "complete_window"
      ],
      "title": "ActivityCoverage",
      "type": "object"
    }
    ```
