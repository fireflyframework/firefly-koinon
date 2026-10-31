<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# InvitationPreview

[All wire models](index.md)

Model aliases: `InvitationPreview`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `tenant_name` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | Yes | Not specified |
| `workspace_name` | `string` or `null` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### role

- Allowed values: `"viewer"`, `"analyst"`, `"editor"`, `"operator"`, `"admin"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "tenant_name": {
          "title": "Tenant Name",
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
          "title": "Workspace Id"
        },
        "workspace_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Workspace Name"
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
        "expires_at": {
          "title": "Expires At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "tenant_name",
        "workspace_id",
        "workspace_name",
        "role",
        "expires_at"
      ],
      "title": "InvitationPreview",
      "type": "object"
    }
    ```
