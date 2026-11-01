<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CommunicationPolicy

[All wire models](index.md)

Model aliases: `CommunicationPolicy`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `revision` | `integer` | Yes | Not specified |
| `sender_id` | `string` or `null` | Yes | Not specified |
| `rules` | Array of [`NotificationPreferenceRule`](notificationpreferencerule.md) | Yes | Not specified |
| `digest_enabled` | `boolean` | Yes | Not specified |
| `can_update` | `boolean` | Yes | Not specified |
| `allowed_digests` | Array of `string` | No | Not specified |
| `default_digest` | `string` | No | `"off"` |
| `default_schedule` | [`DigestSchedule`](digestschedule.md) | No | Not specified |
| `admin_summaries` | Array of [`AdministrativeSummarySchedule`](administrativesummaryschedule.md) | No | Not specified |
| `default_locale` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### allowed_digests

- Each item: Allowed values: `"off"`, `"daily"`, `"weekly"`, `"monthly"`

### default_digest

- Allowed values: `"off"`, `"daily"`, `"weekly"`, `"monthly"`

### admin_summaries

- Maximum items: `3`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "sender_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Sender Id"
        },
        "rules": {
          "items": {
            "$ref": "#/$defs/NotificationPreferenceRule"
          },
          "title": "Rules",
          "type": "array"
        },
        "digest_enabled": {
          "title": "Digest Enabled",
          "type": "boolean"
        },
        "can_update": {
          "title": "Can Update",
          "type": "boolean"
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
        "default_digest": {
          "default": "off",
          "enum": [
            "off",
            "daily",
            "weekly",
            "monthly"
          ],
          "title": "Default Digest",
          "type": "string"
        },
        "default_schedule": {
          "$ref": "#/$defs/DigestSchedule"
        },
        "admin_summaries": {
          "items": {
            "$ref": "#/$defs/AdministrativeSummarySchedule"
          },
          "maxItems": 3,
          "title": "Admin Summaries",
          "type": "array"
        },
        "default_locale": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Default Locale"
        }
      },
      "required": [
        "revision",
        "sender_id",
        "rules",
        "digest_enabled",
        "can_update"
      ],
      "title": "CommunicationPolicy",
      "type": "object"
    }
    ```
