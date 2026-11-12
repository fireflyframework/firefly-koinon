<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceScheduleCapability

[All wire models](index.md)

Model aliases: `SourceScheduleCapability`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `min_interval_seconds` | `integer` | Yes | Not specified |
| `max_interval_seconds` | `integer` | Yes | Not specified |
| `calendar_timezones` | `string` | No | `"iana"` |
| `max_calendar_weekdays` | `integer` | No | `7` |

## Model constraints

- Additional properties: permitted

## Field constraints

### calendar_timezones

- Exact value: `"iana"`

### max_calendar_weekdays

- Exact value: `7`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "min_interval_seconds": {
          "title": "Min Interval Seconds",
          "type": "integer"
        },
        "max_interval_seconds": {
          "title": "Max Interval Seconds",
          "type": "integer"
        },
        "calendar_timezones": {
          "const": "iana",
          "default": "iana",
          "title": "Calendar Timezones",
          "type": "string"
        },
        "max_calendar_weekdays": {
          "const": 7,
          "default": 7,
          "title": "Max Calendar Weekdays",
          "type": "integer"
        }
      },
      "required": [
        "min_interval_seconds",
        "max_interval_seconds"
      ],
      "title": "SourceScheduleCapability",
      "type": "object"
    }
    ```
