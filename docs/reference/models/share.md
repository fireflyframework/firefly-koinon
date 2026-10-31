<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Share

[All wire models](index.md)

Model aliases: `Share`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `revision` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `recipient_policy` | `string` | No | `"organization_current_acl"` |
| `created_at` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `revoked_at` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### revision

- Pattern: `"^[a-f0-9]{64}$"`

### status

- Allowed values: `"active"`, `"revoked"`, `"expired"`

### recipient_policy

- Exact value: `"organization_current_acl"`

### created_at

- Format: `"date-time"`

### expires_at

- Format: `"date-time"`

### revoked_at

- anyOf branch 1 (`string`): Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "revision": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Revision",
          "type": "string"
        },
        "status": {
          "enum": [
            "active",
            "revoked",
            "expired"
          ],
          "title": "Status",
          "type": "string"
        },
        "recipient_policy": {
          "const": "organization_current_acl",
          "default": "organization_current_acl",
          "title": "Recipient Policy",
          "type": "string"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        },
        "revoked_at": {
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
          "title": "Revoked At"
        }
      },
      "required": [
        "id",
        "title",
        "revision",
        "status",
        "created_at",
        "expires_at"
      ],
      "title": "Share",
      "type": "object"
    }
    ```
