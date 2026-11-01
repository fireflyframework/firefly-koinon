<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# InvitationReview

[All wire models](index.md)

Model aliases: `InvitationReview`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `action_reasons` | Map of string keys to `string` | No | Not specified |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `organization_name` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | Yes | Not specified |
| `workspace_name` | `string` or `null` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `can_accept` | `boolean` | Yes | Not specified |
| `can_decline` | `boolean` | Yes | Not specified |
| `binding` | `string` | No | `"directory_identity"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### action_reasons

- Additional properties: `string`
- Each map value: Allowed values: `"closed"`, `"cooldown"`, `"send_limit"`, `"delivery_outcome_unknown"`, `"inviter_authority_lost"`, `"origin_token_revoked"`, `"origin_token_expired"`, `"origin_scope_changed"`, `"recipient_connection_changed"`

### role

- Allowed values: `"viewer"`, `"analyst"`, `"editor"`, `"operator"`, `"admin"`

### expires_at

- Format: `"date-time"`

### status

- Allowed values: `"pending"`, `"accepted"`, `"declined"`, `"revoked"`, `"expired"`

### binding

- Exact value: `"directory_identity"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "action_reasons": {
          "additionalProperties": {
            "enum": [
              "closed",
              "cooldown",
              "send_limit",
              "delivery_outcome_unknown",
              "inviter_authority_lost",
              "origin_token_revoked",
              "origin_token_expired",
              "origin_scope_changed",
              "recipient_connection_changed"
            ],
            "type": "string"
          },
          "propertyNames": {
            "enum": [
              "accept",
              "resend"
            ]
          },
          "title": "Action Reasons",
          "type": "object"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "organization_name": {
          "title": "Organization Name",
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
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        },
        "status": {
          "enum": [
            "pending",
            "accepted",
            "declined",
            "revoked",
            "expired"
          ],
          "title": "Status",
          "type": "string"
        },
        "can_accept": {
          "title": "Can Accept",
          "type": "boolean"
        },
        "can_decline": {
          "title": "Can Decline",
          "type": "boolean"
        },
        "binding": {
          "const": "directory_identity",
          "default": "directory_identity",
          "title": "Binding",
          "type": "string"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "organization_name",
        "workspace_id",
        "workspace_name",
        "role",
        "expires_at",
        "status",
        "can_accept",
        "can_decline"
      ],
      "title": "InvitationReview",
      "type": "object"
    }
    ```
