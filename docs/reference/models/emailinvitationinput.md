<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# EmailInvitationInput

[All wire models](index.md)

Model aliases: `EmailInvitationInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `recipient_ref` | `string` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | No | `null` |
| `expires_in_hours` | `integer` | No | `24` |
| `message` | `string` | No | `""` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### recipient_ref

- Minimum length: `8`
- Maximum length: `4096`

### role

- Allowed values: `"viewer"`, `"analyst"`, `"editor"`, `"operator"`, `"admin"`

### workspace_id

- anyOf branch 1 (`string`): Maximum length: `64`

### expires_in_hours

- Minimum: `1`
- Maximum: `168`

### message

- Maximum length: `1000`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "recipient_ref": {
          "maxLength": 4096,
          "minLength": 8,
          "title": "Recipient Ref",
          "type": "string"
        },
        "role": {
          "enum": [
            "viewer",
            "analyst",
            "editor",
            "operator",
            "admin"
          ],
          "title": "Role",
          "type": "string"
        },
        "workspace_id": {
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
          "title": "Workspace Id"
        },
        "expires_in_hours": {
          "default": 24,
          "maximum": 168,
          "minimum": 1,
          "title": "Expires In Hours",
          "type": "integer"
        },
        "message": {
          "default": "",
          "maxLength": 1000,
          "title": "Message",
          "type": "string"
        }
      },
      "required": [
        "recipient_ref",
        "role"
      ],
      "title": "EmailInvitationInput",
      "type": "object"
    }
    ```
