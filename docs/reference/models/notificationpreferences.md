<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NotificationPreferences

[All wire models](index.md)

Model aliases: `NotificationPreferences`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `admin_summaries_available` | `boolean` | No | `false` |
| `admin_summaries_enabled` | `boolean` | No | `false` |
| `revision` | `integer` | Yes | Not specified |
| `rules` | Array of [`NotificationPreferenceRule`](notificationpreferencerule.md) | Yes | Not specified |
| `digest` | `string` | Yes | Not specified |
| `allowed_digests` | Array of `string` | Yes | Not specified |
| `locale` | `string` | Yes | Not specified |
| `time_zone` | `string` | Yes | Not specified |
| `schedule` | [`DigestSchedule`](digestschedule.md) | No | Not specified |
| `next_run_at` | `string` or `null` | No | `null` |
| `next_run_local` | `string` or `null` | No | `null` |
| `admin_summaries` | `boolean` or `null` | No | `null` |
| `notification_locale` | `string` or `null` | No | `null` |
| `effective_locale` | `string` | No | `"en-US"` |
| `locale_origin` | `string` | No | `"default"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### digest

- Allowed values: `"off"`, `"daily"`, `"weekly"`, `"monthly"`

### allowed_digests

- Each item: Allowed values: `"off"`, `"daily"`, `"weekly"`, `"monthly"`

### next_run_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### locale_origin

- Allowed values: `"user"`, `"organization"`, `"installation"`, `"default"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "admin_summaries_available": {
          "default": false,
          "title": "Admin Summaries Available",
          "type": "boolean"
        },
        "admin_summaries_enabled": {
          "default": false,
          "title": "Admin Summaries Enabled",
          "type": "boolean"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "rules": {
          "items": {
            "$ref": "#/$defs/NotificationPreferenceRule"
          },
          "title": "Rules",
          "type": "array"
        },
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
        "allowed_digests": {
          "items": {
            "enum": [
              "off",
              "daily",
              "weekly",
              "monthly"
            ],
            "type": "string"
          },
          "title": "Allowed Digests",
          "type": "array"
        },
        "locale": {
          "title": "Locale",
          "type": "string"
        },
        "time_zone": {
          "title": "Time Zone",
          "type": "string"
        },
        "schedule": {
          "$ref": "#/$defs/DigestSchedule"
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
          "default": null,
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
          "default": null,
          "title": "Next Run Local"
        },
        "admin_summaries": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Admin Summaries"
        },
        "notification_locale": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Notification Locale"
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
        "revision",
        "rules",
        "digest",
        "allowed_digests",
        "locale",
        "time_zone"
      ],
      "title": "NotificationPreferences",
      "type": "object"
    }
    ```
