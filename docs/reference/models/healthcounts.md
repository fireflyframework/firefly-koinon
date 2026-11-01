<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# HealthCounts

[All wire models](index.md)

Model aliases: `HealthCounts`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `observed_total` | `integer` | Yes | Not specified |
| `observed_ready` | `integer` | No | `0` |
| `observed_pending` | `integer` | No | `0` |
| `observed_running` | `integer` | No | `0` |
| `observed_failed` | `integer` | No | `0` |

## Model constraints

- Additional properties: permitted

## Field constraints

### observed_total

- Minimum: `0`
- Maximum: `1000`

### observed_ready

- Minimum: `0`
- Maximum: `1000`

### observed_pending

- Minimum: `0`
- Maximum: `1000`

### observed_running

- Minimum: `0`
- Maximum: `1000`

### observed_failed

- Minimum: `0`
- Maximum: `1000`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "observed_total": {
          "maximum": 1000,
          "minimum": 0,
          "title": "Observed Total",
          "type": "integer"
        },
        "observed_ready": {
          "default": 0,
          "maximum": 1000,
          "minimum": 0,
          "title": "Observed Ready",
          "type": "integer"
        },
        "observed_pending": {
          "default": 0,
          "maximum": 1000,
          "minimum": 0,
          "title": "Observed Pending",
          "type": "integer"
        },
        "observed_running": {
          "default": 0,
          "maximum": 1000,
          "minimum": 0,
          "title": "Observed Running",
          "type": "integer"
        },
        "observed_failed": {
          "default": 0,
          "maximum": 1000,
          "minimum": 0,
          "title": "Observed Failed",
          "type": "integer"
        }
      },
      "required": [
        "observed_total"
      ],
      "title": "HealthCounts",
      "type": "object"
    }
    ```
