<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DigestSchedule

[All wire models](index.md)

Model aliases: `DigestSchedule`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `local_time` | `string` | No | `"09:00"` |
| `weekday` | `integer` | No | `0` |
| `day_of_month` | `integer` | No | `1` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### local_time

- Pattern: <code>&#34;&#94;&#40;&#63;&#58;&#91;01&#93;&#91;0&#45;9&#93;&#124;2&#91;0&#45;3&#93;&#41;&#58;&#91;0&#45;5&#93;&#91;0&#45;9&#93;&#36;&#34;</code>

### weekday

- Minimum: `0`
- Maximum: `6`

### day_of_month

- Minimum: `1`
- Maximum: `31`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "local_time": {
          "default": "09:00",
          "pattern": "^(?:[01][0-9]|2[0-3]):[0-5][0-9]$",
          "title": "Local Time",
          "type": "string"
        },
        "weekday": {
          "default": 0,
          "maximum": 6,
          "minimum": 0,
          "title": "Weekday",
          "type": "integer"
        },
        "day_of_month": {
          "default": 1,
          "maximum": 31,
          "minimum": 1,
          "title": "Day Of Month",
          "type": "integer"
        }
      },
      "title": "DigestSchedule",
      "type": "object"
    }
    ```
