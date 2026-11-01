<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# PlatformHealth

[All wire models](index.md)

Model aliases: `PlatformHealth`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `checked_at` | `string` | Yes | Not specified |
| `summary` | [`HealthSummary`](healthsummary.md) | No | Not specified |
| `components` | Array of [`HealthComponent`](healthcomponent.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### checked_at

- Format: `"date-time"`

### components

- Maximum items: `16`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "checked_at": {
          "format": "date-time",
          "title": "Checked At",
          "type": "string"
        },
        "summary": {
          "$ref": "#/$defs/HealthSummary"
        },
        "components": {
          "items": {
            "$ref": "#/$defs/HealthComponent"
          },
          "maxItems": 16,
          "title": "Components",
          "type": "array"
        }
      },
      "required": [
        "tenant_id",
        "checked_at",
        "components"
      ],
      "title": "PlatformHealth",
      "type": "object"
    }
    ```
