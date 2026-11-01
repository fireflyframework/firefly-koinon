<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DeliveryRecord

[All wire models](index.md)

Model aliases: `DeliveryRecord`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `channel` | `string` | No | `"email"` |
| `invitation_id` | `string` or `null` | Yes | Not specified |
| `membership_id` | `string` or `null` | Yes | Not specified |
| `recipient_display` | `string` | Yes | Not specified |
| `scope_name` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `last_attempt_at` | `string` or `null` | Yes | Not specified |
| `next_attempt_at` | `string` or `null` | Yes | Not specified |
| `attempt_count` | `integer` | Yes | Not specified |
| `failure_code` | `string` or `null` | Yes | Not specified |
| `safe_explanation` | `string` or `null` | Yes | Not specified |
| `can_retry` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"invitation"`, `"access_granted"`, `"role_changed"`, `"access_removed"`, `"security"`, `"welcome"`, `"digest"`

### channel

- Exact value: `"email"`

### status

- Allowed values: `"queued"`, `"sending"`, `"sent"`, `"delivered"`, `"deferred"`, `"failed"`, `"suppressed"`, `"cancelled"`, `"unknown"`

### created_at

- Format: `"date-time"`

### last_attempt_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### next_attempt_at

- anyOf branch 1 (`string`): Format: `"date-time"`


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
        "kind": {
          "enum": [
            "invitation",
            "access_granted",
            "role_changed",
            "access_removed",
            "security",
            "welcome",
            "digest"
          ],
          "title": "Kind",
          "type": "string"
        },
        "channel": {
          "const": "email",
          "default": "email",
          "title": "Channel",
          "type": "string"
        },
        "invitation_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Invitation Id"
        },
        "membership_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Membership Id"
        },
        "recipient_display": {
          "title": "Recipient Display",
          "type": "string"
        },
        "scope_name": {
          "title": "Scope Name",
          "type": "string"
        },
        "status": {
          "enum": [
            "queued",
            "sending",
            "sent",
            "delivered",
            "deferred",
            "failed",
            "suppressed",
            "cancelled",
            "unknown"
          ],
          "title": "Status",
          "type": "string"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "last_attempt_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Last Attempt At"
        },
        "next_attempt_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Next Attempt At"
        },
        "attempt_count": {
          "title": "Attempt Count",
          "type": "integer"
        },
        "failure_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Failure Code"
        },
        "safe_explanation": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Safe Explanation"
        },
        "can_retry": {
          "title": "Can Retry",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "kind",
        "invitation_id",
        "membership_id",
        "recipient_display",
        "scope_name",
        "status",
        "created_at",
        "last_attempt_at",
        "next_attempt_at",
        "attempt_count",
        "failure_code",
        "safe_explanation",
        "can_retry"
      ],
      "title": "DeliveryRecord",
      "type": "object"
    }
    ```
