<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ActivityWindow

[All wire models](index.md)

Model aliases: `ActivityWindow`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `start_at` | `string` | Yes | Not specified |
| `end_at` | `string` | Yes | Not specified |
| `time_zone` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### start_at

- Format: `"date-time"`

### end_at

- Format: `"date-time"`

### time_zone

- Minimum length: `1`
- Maximum length: `128`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "start_at": {
          "format": "date-time",
          "title": "Start At",
          "type": "string"
        },
        "end_at": {
          "format": "date-time",
          "title": "End At",
          "type": "string"
        },
        "time_zone": {
          "maxLength": 128,
          "minLength": 1,
          "title": "Time Zone",
          "type": "string"
        }
      },
      "required": [
        "start_at",
        "end_at",
        "time_zone"
      ],
      "title": "ActivityWindow",
      "type": "object"
    }
    ```
