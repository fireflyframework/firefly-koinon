<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DigestSchedulePreview

[All wire models](index.md)

Model aliases: `DigestSchedulePreview`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `digest` | `string` | Yes | Not specified |
| `schedule` | [`DigestSchedule`](digestschedule.md) | Yes | Not specified |
| `time_zone` | `string` | Yes | Not specified |
| `next_run_at` | `string` or `null` | Yes | Not specified |
| `next_run_local` | `string` or `null` | Yes | Not specified |
| `window_start` | `string` or `null` | Yes | Not specified |
| `window_end` | `string` or `null` | Yes | Not specified |
| `dst_policy` | `string` | No | `"first_valid_minute_earlier_fold"` |
| `effective_locale` | `string` | No | `"en-US"` |
| `locale_origin` | `string` | No | `"default"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### digest

- Allowed values: `"off"`, `"daily"`, `"weekly"`, `"monthly"`

### next_run_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### window_start

- anyOf branch 1 (`string`): Format: `"date-time"`

### window_end

- anyOf branch 1 (`string`): Format: `"date-time"`

### dst_policy

- Exact value: `"first_valid_minute_earlier_fold"`

### locale_origin

- Allowed values: `"user"`, `"organization"`, `"installation"`, `"default"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "digest": {
          "enum": [
            "off",
            "daily",
            "weekly",
            "monthly"
          ],
          "title": "Digest",
          "type": "string"
        },
        "schedule": {
          "$ref": "#/$defs/DigestSchedule"
        },
        "time_zone": {
          "title": "Time Zone",
          "type": "string"
        },
        "next_run_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Next Run At"
        },
        "next_run_local": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Next Run Local"
        },
        "window_start": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Window Start"
        },
        "window_end": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Window End"
        },
        "dst_policy": {
          "const": "first_valid_minute_earlier_fold",
          "default": "first_valid_minute_earlier_fold",
          "title": "Dst Policy",
          "type": "string"
        },
        "effective_locale": {
          "default": "en-US",
          "title": "Effective Locale",
          "type": "string"
        },
        "locale_origin": {
          "default": "default",
          "enum": [
            "user",
            "organization",
            "installation",
            "default"
          ],
          "title": "Locale Origin",
          "type": "string"
        }
      },
      "required": [
        "digest",
        "schedule",
        "time_zone",
        "next_run_at",
        "next_run_local",
        "window_start",
        "window_end"
      ],
      "title": "DigestSchedulePreview",
      "type": "object"
    }
    ```
