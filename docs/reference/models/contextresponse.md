<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ContextResponse

[All wire models](index.md)

Model aliases: `ContextResponse`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `workspace_permissions` | Map of string keys to Array of `string` or `null` | No | `null` |
| `subject` | `string` | Yes | Not specified |
| `tenants` | Array of [`TenantContext`](tenantcontext.md) | No | Not specified |
| `memberships` | Array of [`Membership`](membership.md) | No | Not specified |
| `workspaces` | Array of [`CatalogEntry`](catalogentry.md) | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### workspace_permissions

- anyOf branch 1 (Map of string keys to Array of `string`): Additional properties: Array of `string`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "workspace_permissions": {
          "anyOf": [
            {
              "additionalProperties": {
                "items": {
                  "type": "string"
                },
                "type": "array"
              },
              "type": "object"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Workspace Permissions"
        },
        "subject": {
          "title": "Subject",
          "type": "string"
        },
        "tenants": {
          "items": {
            "$ref": "#/$defs/TenantContext"
          },
          "title": "Tenants",
          "type": "array"
        },
        "memberships": {
          "items": {
            "$ref": "#/$defs/Membership"
          },
          "title": "Memberships",
          "type": "array"
        },
        "workspaces": {
          "items": {
            "$ref": "#/$defs/CatalogEntry"
          },
          "title": "Workspaces",
          "type": "array"
        }
      },
      "required": [
        "subject"
      ],
      "title": "ContextResponse",
      "type": "object"
    }
    ```
