<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CalendarSchedule

[All wire models](index.md)

Model aliases: `CalendarSchedule`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `timezone` | `string` | Yes | Not specified |
| `time` | `string` | Yes | Not specified |
| `weekdays` | Array of `integer` | No | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### kind

- Exact value: `"calendar"`

### timezone

- Minimum length: `1`
- Maximum length: `255`

### time

- Pattern: <code>&#34;&#94;&#40;&#63;&#58;&#91;01&#93;&#91;0&#45;9&#93;&#124;2&#91;0&#45;3&#93;&#41;&#58;&#91;0&#45;5&#93;&#91;0&#45;9&#93;&#36;&#34;</code>

### weekdays

- Minimum items: `1`
- Maximum items: `7`
- Each item: Minimum: `1`
- Each item: Maximum: `7`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "calendar",
          "title": "Kind",
          "type": "string"
        },
        "timezone": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Timezone",
          "type": "string"
        },
        "time": {
          "pattern": "^(?:[01][0-9]|2[0-3]):[0-5][0-9]$",
          "title": "Time",
          "type": "string"
        },
        "weekdays": {
          "items": {
            "maximum": 7,
            "minimum": 1,
            "type": "integer"
          },
          "maxItems": 7,
          "minItems": 1,
          "title": "Weekdays",
          "type": "array"
        }
      },
      "required": [
        "kind",
        "timezone",
        "time"
      ],
      "title": "CalendarSchedule",
      "type": "object"
    }
    ```
