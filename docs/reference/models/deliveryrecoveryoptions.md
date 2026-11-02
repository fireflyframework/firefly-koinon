<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DeliveryRecoveryOptions

[All wire models](index.md)

Model aliases: `DeliveryRecoveryOptions`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `delivery_id` | `string` | Yes | Not specified |
| `generation` | `integer` | Yes | Not specified |
| `submission_status` | `string` | Yes | Not specified |
| `attempt_count` | `integer` | Yes | Not specified |
| `can_inspect` | `boolean` | Yes | Not specified |
| `inspection_reason` | `string` or `null` | No | `null` |
| `provider_binding_state` | `string` | Yes | Not specified |
| `can_recover_welcome` | `boolean` | Yes | Not specified |
| `recovery_reason` | `string` or `null` | No | `null` |
| `contact_id` | `string` or `null` | No | `null` |
| `contact_revision` | `integer` or `null` | No | `null` |
| `possible_original_late_arrival` | `boolean` | No | `true` |

## Model constraints

- Additional properties: permitted

## Field constraints

### submission_status

- Allowed values: `"queued"`, `"sending"`, `"sent"`, `"delivered"`, `"deferred"`, `"failed"`, `"suppressed"`, `"cancelled"`, `"unknown"`

### provider_binding_state

- Allowed values: `"verified"`, `"operator_verification_required"`, `"unavailable"`

### possible_original_late_arrival

- Exact value: `true`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "delivery_id": {
          "title": "Delivery Id",
          "type": "string"
        },
        "generation": {
          "title": "Generation",
          "type": "integer"
        },
        "submission_status": {
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
          "title": "Submission Status",
          "type": "string"
        },
        "attempt_count": {
          "title": "Attempt Count",
          "type": "integer"
        },
        "can_inspect": {
          "title": "Can Inspect",
          "type": "boolean"
        },
        "inspection_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Inspection Reason"
        },
        "provider_binding_state": {
          "enum": [
            "verified",
            "operator_verification_required",
            "unavailable"
          ],
          "title": "Provider Binding State",
          "type": "string"
        },
        "can_recover_welcome": {
          "title": "Can Recover Welcome",
          "type": "boolean"
        },
        "recovery_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Recovery Reason"
        },
        "contact_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Contact Id"
        },
        "contact_revision": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Contact Revision"
        },
        "possible_original_late_arrival": {
          "const": true,
          "default": true,
          "title": "Possible Original Late Arrival",
          "type": "boolean"
        }
      },
      "required": [
        "delivery_id",
        "generation",
        "submission_status",
        "attempt_count",
        "can_inspect",
        "provider_binding_state",
        "can_recover_welcome"
      ],
      "title": "DeliveryRecoveryOptions",
      "type": "object"
    }
    ```
