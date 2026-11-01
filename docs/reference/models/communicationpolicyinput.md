<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CommunicationPolicyInput

[All wire models](index.md)

Model aliases: `CommunicationPolicyInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `sender_id` | `string` or `null` | No | `null` |
| `rules` | Array of [`NotificationPreferenceRuleInput`](notificationpreferenceruleinput.md) | Yes | Not specified |
| `digest_enabled` | `boolean` | No | `false` |
| `allowed_digests` | Array of `string` | No | Not specified |
| `default_digest` | `string` | No | `"off"` |
| `default_schedule` | [`DigestSchedule`](digestschedule.md) | No | Not specified |
| `admin_summaries` | Array of [`AdministrativeSummarySchedule`](administrativesummaryschedule.md) | No | Not specified |
| `default_locale` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `0`

### sender_id

- anyOf branch 1 (`string`): Maximum length: `64`

### rules

- Maximum items: `7`

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
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "minimum": 0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "sender_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sender Id"
        },
        "rules": {
          "items": {
            "$ref": "#/$defs/NotificationPreferenceRuleInput"
          },
          "maxItems": 7,
          "title": "Rules",
          "type": "array"
        },
        "digest_enabled": {
          "default": false,
          "title": "Digest Enabled",
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
        "expected_revision",
        "rules"
      ],
      "title": "CommunicationPolicyInput",
      "type": "object"
    }
    ```
