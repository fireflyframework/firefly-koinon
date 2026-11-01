<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# HealthSummary

[All wire models](index.md)

Model aliases: `HealthSummary`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `passed` | `integer` | No | `0` |
| `failed` | `integer` | No | `0` |
| `unknown` | `integer` | No | `0` |
| `disabled` | `integer` | No | `0` |

## Model constraints

- Additional properties: permitted

## Field constraints

### passed

- Minimum: `0`
- Maximum: `16`

### failed

- Minimum: `0`
- Maximum: `16`

### unknown

- Minimum: `0`
- Maximum: `16`

### disabled

- Minimum: `0`
- Maximum: `16`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "passed": {
          "default": 0,
          "maximum": 16,
          "minimum": 0,
          "title": "Passed",
          "type": "integer"
        },
        "failed": {
          "default": 0,
          "maximum": 16,
          "minimum": 0,
          "title": "Failed",
          "type": "integer"
        },
        "unknown": {
          "default": 0,
          "maximum": 16,
          "minimum": 0,
          "title": "Unknown",
          "type": "integer"
        },
        "disabled": {
          "default": 0,
          "maximum": 16,
          "minimum": 0,
          "title": "Disabled",
          "type": "integer"
        }
      },
      "title": "HealthSummary",
      "type": "object"
    }
    ```
