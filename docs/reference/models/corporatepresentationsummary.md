<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CorporatePresentationSummary

[All wire models](index.md)

Model aliases: `CorporatePresentationSummary`.

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
        }
      },
      "title": "CorporatePresentationSummary",
      "type": "object"
    }
    ```
