<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# EmailInvitation

[All wire models](index.md)

Model aliases: `EmailInvitation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `action_reasons` | Map of string keys to `string` | No | Not specified |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | Yes | Not specified |
| `organization_name` | `string` | Yes | Not specified |
| `workspace_name` | `string` or `null` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `recipient_display_name` | `string` | Yes | Not specified |
| `recipient_email` | `string` | Yes | Not specified |
| `provider_label` | `string` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `accepted_at` | `string` or `null` | No | `null` |
| `declined_at` | `string` or `null` | No | `null` |
| `revoked_at` | `string` or `null` | No | `null` |
| `delivery` | [`InvitationDelivery`](invitationdelivery.md) | Yes | Not specified |
| `allowed_actions` | Array of `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### action_reasons

- Additional properties: `string`
- Each map value: Allowed values: `"closed"`, `"cooldown"`, `"send_limit"`, `"delivery_outcome_unknown"`, `"inviter_authority_lost"`, `"origin_token_revoked"`, `"origin_token_expired"`, `"origin_scope_changed"`, `"recipient_connection_changed"`

### role

- Allowed values: `"viewer"`, `"analyst"`, `"editor"`, `"operator"`, `"admin"`

### created_at

- Format: `"date-time"`

### expires_at

- Format: `"date-time"`

### status

- Allowed values: `"pending"`, `"accepted"`, `"declined"`, `"revoked"`, `"expired"`

### accepted_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### declined_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### revoked_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### allowed_actions

- Each item: Allowed values: `"revoke"`, `"resend"`


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
        "organization_name": {
          "title": "Organization Name",
          "type": "string"
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
        "recipient_display_name": {
          "title": "Recipient Display Name",
          "type": "string"
        },
        "recipient_email": {
          "title": "Recipient Email",
          "type": "string"
        },
        "provider_label": {
          "title": "Provider Label",
          "type": "string"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
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
        "accepted_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Accepted At"
        },
        "declined_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Declined At"
        },
        "revoked_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Revoked At"
        },
        "delivery": {
          "$ref": "#/$defs/InvitationDelivery"
        },
        "allowed_actions": {
          "items": {
            "enum": [
              "revoke",
              "resend"
            ],
            "type": "string"
          },
          "title": "Allowed Actions",
          "type": "array"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "workspace_id",
        "organization_name",
        "workspace_name",
        "role",
        "recipient_display_name",
        "recipient_email",
        "provider_label",
        "created_at",
        "expires_at",
        "status",
        "delivery",
        "allowed_actions"
      ],
      "title": "EmailInvitation",
      "type": "object"
    }
    ```
