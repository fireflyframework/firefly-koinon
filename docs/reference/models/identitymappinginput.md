<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IdentityMappingInput

[All wire models](index.md)

Model aliases: `IdentityMappingInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `group_id` | `string` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | No | `null` |
| `enabled` | `boolean` | No | `true` |
| `expected_revision` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### group_id

- Minimum length: `1`
- Maximum length: `256`

### role

- Allowed values: `"viewer"`, `"analyst"`, `"editor"`, `"operator"`, `"admin"`

### workspace_id

- anyOf branch 1 (`string`): Maximum length: `64`

### expected_revision

- anyOf branch 1 (`integer`): Minimum: `1`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "group_id": {
          "maxLength": 256,
          "minLength": 1,
          "title": "Group Id",
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
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "expected_revision": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Revision"
        }
      },
      "required": [
        "group_id",
        "role"
      ],
      "title": "IdentityMappingInput",
      "type": "object"
    }
    ```
