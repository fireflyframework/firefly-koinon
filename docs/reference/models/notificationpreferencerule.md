<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NotificationPreferenceRule

[All wire models](index.md)

Model aliases: `NotificationPreferenceRule`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `required` | `boolean` | Yes | Not specified |
| `inbox` | `boolean` | Yes | Not specified |
| `email` | `boolean` | Yes | Not specified |
| `email_available` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"invitation"`, `"access_granted"`, `"role_changed"`, `"access_removed"`, `"security"`, `"welcome"`, `"digest"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "kind": {
          "enum": [
            "invitation",
            "access_granted",
            "role_changed",
            "access_removed",
            "security",
            "welcome",
            "digest"
          ],
          "title": "Kind",
          "type": "string"
        },
        "required": {
          "title": "Required",
          "type": "boolean"
        },
        "inbox": {
          "title": "Inbox",
          "type": "boolean"
        },
        "email": {
          "title": "Email",
          "type": "boolean"
        },
        "email_available": {
          "title": "Email Available",
          "type": "boolean"
        }
      },
      "required": [
        "kind",
        "required",
        "inbox",
        "email",
        "email_available"
      ],
      "title": "NotificationPreferenceRule",
      "type": "object"
    }
    ```
