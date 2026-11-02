<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# WelcomeRecoveryAcknowledgement

[All wire models](index.md)

Model aliases: `WelcomeRecoveryAcknowledgement`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `original_delivery_id` | `string` | Yes | Not specified |
| `delivery_id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `possible_original_late_arrival` | `boolean` | No | `true` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"queued"`, `"sending"`, `"sent"`, `"delivered"`, `"deferred"`, `"failed"`, `"suppressed"`, `"cancelled"`, `"unknown"`

### possible_original_late_arrival

- Exact value: `true`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "original_delivery_id": {
          "title": "Original Delivery Id",
          "type": "string"
        },
        "delivery_id": {
          "title": "Delivery Id",
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
        "possible_original_late_arrival": {
          "const": true,
          "default": true,
          "title": "Possible Original Late Arrival",
          "type": "boolean"
        }
      },
      "required": [
        "original_delivery_id",
        "delivery_id",
        "status"
      ],
      "title": "WelcomeRecoveryAcknowledgement",
      "type": "object"
    }
    ```
