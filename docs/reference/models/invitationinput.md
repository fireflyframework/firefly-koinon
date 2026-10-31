<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# InvitationInput

[All wire models](index.md)

Model aliases: `InvitationInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `role` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | No | `null` |
| `expires_in_hours` | `integer` | No | `24` |
| `label` | `string` | No | `""` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### role

- Allowed values: `"viewer"`, `"analyst"`, `"editor"`, `"operator"`, `"admin"`

### expires_in_hours

- Minimum: `1`
- Maximum: `168`

### label

- Maximum length: `120`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
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
        "label": {
          "default": "",
          "maxLength": 120,
          "title": "Label",
          "type": "string"
        }
      },
      "required": [
        "role"
      ],
      "title": "InvitationInput",
      "type": "object"
    }
    ```
