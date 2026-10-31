<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Invitation

[All wire models](index.md)

Model aliases: `Invitation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `label` | `string` | Yes | Not specified |
| `created_by` | `string` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `accepted_at` | `string` or `null` | No | `null` |
| `accepted_by` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### role

- Allowed values: `"viewer"`, `"analyst"`, `"editor"`, `"operator"`, `"admin"`

### status

- Allowed values: `"pending"`, `"accepted"`, `"expired"`, `"revoked"`


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
        "label": {
          "title": "Label",
          "type": "string"
        },
        "created_by": {
          "title": "Created By",
          "type": "string"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "expires_at": {
          "title": "Expires At",
          "type": "string"
        },
        "status": {
          "enum": [
            "pending",
            "accepted",
            "expired",
            "revoked"
          ],
          "title": "Status",
          "type": "string"
        },
        "accepted_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Accepted At"
        },
        "accepted_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Accepted By"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "workspace_id",
        "role",
        "label",
        "created_by",
        "created_at",
        "expires_at",
        "status"
      ],
      "title": "Invitation",
      "type": "object"
    }
    ```
