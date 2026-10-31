<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Membership

[All wire models](index.md)

Model aliases: `Membership`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `managed` | `boolean` | No | `false` |
| `origin` | `string` | No | `"manual"` |
| `source_id` | `string` or `null` | No | `null` |
| `source_name` | `string` or `null` | No | `null` |
| `expires_at` | `string` or `null` | No | `null` |
| `id` | `string` | Yes | Not specified |
| `subject` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | No | `null` |
| `role` | `string` | Yes | Not specified |
| `active` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### origin

- Allowed values: `"manual"`, `"corporate"`

### role

- Allowed values: `"viewer"`, `"analyst"`, `"editor"`, `"operator"`, `"admin"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "managed": {
          "default": false,
          "title": "Managed",
          "type": "boolean"
        },
        "origin": {
          "default": "manual",
          "enum": [
            "manual",
            "corporate"
          ],
          "title": "Origin",
          "type": "string"
        },
        "source_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Id"
        },
        "source_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Name"
        },
        "expires_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expires At"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "subject": {
          "title": "Subject",
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
          "default": null,
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
        "active": {
          "title": "Active",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "subject",
        "tenant_id",
        "role",
        "active"
      ],
      "title": "Membership",
      "type": "object"
    }
    ```
