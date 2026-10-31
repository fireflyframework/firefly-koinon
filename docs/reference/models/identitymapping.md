<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IdentityMapping

[All wire models](index.md)

Model aliases: `IdentityMapping`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `provider_id` | `string` | Yes | Not specified |
| `group_id` | `string` | Yes | Not specified |
| `group_name` | `string` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | Yes | Not specified |
| `enabled` | `boolean` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |

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
        "provider_id": {
          "title": "Provider Id",
          "type": "string"
        },
        "group_id": {
          "title": "Group Id",
          "type": "string"
        },
        "group_name": {
          "title": "Group Name",
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
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Workspace Id"
        },
        "enabled": {
          "title": "Enabled",
          "type": "boolean"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "provider_id",
        "group_id",
        "group_name",
        "role",
        "workspace_id",
        "enabled",
        "revision"
      ],
      "title": "IdentityMapping",
      "type": "object"
    }
    ```
