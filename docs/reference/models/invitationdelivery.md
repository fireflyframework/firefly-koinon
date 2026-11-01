<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# InvitationDelivery

[All wire models](index.md)

Model aliases: `InvitationDelivery`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `queued_at` | `string` | Yes | Not specified |
| `last_attempt_at` | `string` or `null` | No | `null` |
| `next_attempt_at` | `string` or `null` | No | `null` |
| `next_resend_at` | `string` or `null` | No | `null` |
| `failure_code` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"queued"`, `"sending"`, `"sent"`, `"delivered"`, `"deferred"`, `"failed"`, `"suppressed"`, `"cancelled"`, `"unknown"`

### queued_at

- Format: `"date-time"`

### last_attempt_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### next_attempt_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### next_resend_at

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
        "queued_at": {
          "format": "date-time",
          "title": "Queued At",
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
          "default": null,
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
          "default": null,
          "title": "Next Attempt At"
        },
        "next_resend_at": {
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
          "title": "Next Resend At"
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
          "default": null,
          "title": "Failure Code"
        }
      },
      "required": [
        "id",
        "status",
        "queued_at"
      ],
      "title": "InvitationDelivery",
      "type": "object"
    }
    ```
