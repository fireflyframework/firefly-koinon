<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NotificationPreferencesInput

[All wire models](index.md)

Model aliases: `NotificationPreferencesInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `rules` | Array of [`NotificationPreferenceRuleInput`](notificationpreferenceruleinput.md) | Yes | Not specified |
| `digest` | `string` | Yes | Not specified |
| `schedule` | [`DigestSchedule`](digestschedule.md) | No | Not specified |
| `admin_summaries` | `boolean` or `null` | No | `null` |
| `notification_locale` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `0`

### rules

- Maximum items: `7`

### digest

- Allowed values: `"off"`, `"daily"`, `"weekly"`, `"monthly"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "minimum": 0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "rules": {
          "items": {
            "$ref": "#/$defs/NotificationPreferenceRuleInput"
          },
          "maxItems": 7,
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
        "schedule": {
          "$ref": "#/$defs/DigestSchedule"
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
        }
      },
      "required": [
        "expected_revision",
        "rules",
        "digest"
      ],
      "title": "NotificationPreferencesInput",
      "type": "object"
    }
    ```
