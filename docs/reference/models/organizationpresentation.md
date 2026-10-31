<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationPresentation

[All wire models](index.md)

Model aliases: `OrganizationPresentation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name_source` | `string` | No | `"personal"` |
| `avatar_source` | `string` | No | `"personal"` |
| `provider_id` | `string` or `null` | No | `null` |
| `provider_name` | `string` or `null` | No | `null` |
| `status` | `string` | No | `"not_configured"` |
| `last_synced_at` | `string` or `null` | No | `null` |
| `corporate_department` | `string` or `null` | No | `null` |
| `tenant_id` | `string` | Yes | Not specified |
| `profile_id` | `string` or `null` | No | `null` |
| `revision` | `integer` | No | `0` |
| `name_mode` | `string` | No | `"organization"` |
| `avatar_mode` | `string` | No | `"organization"` |
| `allow_personal_overrides` | `boolean` | No | `true` |
| `display_name` | `string` | No | `""` |
| `avatar_url` | `string` or `null` | No | `null` |
| `avatar_version` | `string` or `null` | No | `null` |
| `last_attempt_at` | `string` or `null` | No | `null` |
| `fields` | Array of [`CorporateProfileFieldObservation`](corporateprofilefieldobservation.md) | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### name_source

- Allowed values: `"organization"`, `"personal"`

### avatar_source

- Allowed values: `"organization"`, `"personal"`

### status

- Allowed values: `"not_configured"`, `"not_bound"`, `"queued"`, `"running"`, `"current"`, `"stale"`, `"unavailable"`, `"conflict"`

### last_synced_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### corporate_department

- anyOf branch 1 (`string`): Maximum length: `160`

### revision

- Minimum: `0`
- Maximum: `2147483647`

### name_mode

- Allowed values: `"organization"`, `"personal"`

### avatar_mode

- Allowed values: `"organization"`, `"personal"`

### display_name

- Maximum length: `256`

### last_attempt_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### fields

- Maximum items: `5`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "name_source": {
          "default": "personal",
          "enum": [
            "organization",
            "personal"
          ],
          "title": "Name Source",
          "type": "string"
        },
        "avatar_source": {
          "default": "personal",
          "enum": [
            "organization",
            "personal"
          ],
          "title": "Avatar Source",
          "type": "string"
        },
        "provider_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Provider Id"
        },
        "provider_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Provider Name"
        },
        "status": {
          "default": "not_configured",
          "enum": [
            "not_configured",
            "not_bound",
            "queued",
            "running",
            "current",
            "stale",
            "unavailable",
            "conflict"
          ],
          "title": "Status",
          "type": "string"
        },
        "last_synced_at": {
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
          "title": "Last Synced At"
        },
        "corporate_department": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Corporate Department"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "profile_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Profile Id"
        },
        "revision": {
          "default": 0,
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Revision",
          "type": "integer"
        },
        "name_mode": {
          "default": "organization",
          "enum": [
            "organization",
            "personal"
          ],
          "title": "Name Mode",
          "type": "string"
        },
        "avatar_mode": {
          "default": "organization",
          "enum": [
            "organization",
            "personal"
          ],
          "title": "Avatar Mode",
          "type": "string"
        },
        "allow_personal_overrides": {
          "default": true,
          "title": "Allow Personal Overrides",
          "type": "boolean"
        },
        "display_name": {
          "default": "",
          "maxLength": 256,
          "title": "Display Name",
          "type": "string"
        },
        "avatar_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Avatar Url"
        },
        "avatar_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Avatar Version"
        },
        "last_attempt_at": {
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
          "title": "Last Attempt At"
        },
        "fields": {
          "items": {
            "$ref": "#/$defs/CorporateProfileFieldObservation"
          },
          "maxItems": 5,
          "title": "Fields",
          "type": "array"
        }
      },
      "required": [
        "tenant_id"
      ],
      "title": "OrganizationPresentation",
      "type": "object"
    }
    ```
