<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IntervalSchedule

[All wire models](index.md)

Model aliases: `IntervalSchedule`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `seconds` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### kind

- Exact value: `"interval"`

### seconds

- Minimum: `900`
- Maximum: `604800`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "interval",
          "title": "Kind",
          "type": "string"
        },
        "seconds": {
          "maximum": 604800,
          "minimum": 900,
          "title": "Seconds",
          "type": "integer"
        }
      },
      "required": [
        "kind",
        "seconds"
      ],
      "title": "IntervalSchedule",
      "type": "object"
    }
    ```
