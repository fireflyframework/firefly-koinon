<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DeliveryOperationObservation

[All wire models](index.md)

Model aliases: `DeliveryOperationObservation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `delivery_id` | `string` | Yes | Not specified |
| `source` | `string` | No | `"operation_lookup"` |
| `operation_state` | `string` | Yes | Not specified |
| `recipient_state` | `string` | No | `"not_observed"` |
| `checked_at` | `string` or `null` | No | `null` |
| `reason_code` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### source

- Exact value: `"operation_lookup"`

### operation_state

- Allowed values: `"checking"`, `"pending"`, `"accepted"`, `"rejected"`, `"unknown"`, `"unavailable"`

### recipient_state

- Exact value: `"not_observed"`

### checked_at

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
        "delivery_id": {
          "title": "Delivery Id",
          "type": "string"
        },
        "source": {
          "const": "operation_lookup",
          "default": "operation_lookup",
          "title": "Source",
          "type": "string"
        },
        "operation_state": {
          "enum": [
            "checking",
            "pending",
            "accepted",
            "rejected",
            "unknown",
            "unavailable"
          ],
          "title": "Operation State",
          "type": "string"
        },
        "recipient_state": {
          "const": "not_observed",
          "default": "not_observed",
          "title": "Recipient State",
          "type": "string"
        },
        "checked_at": {
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
          "title": "Checked At"
        },
        "reason_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason Code"
        }
      },
      "required": [
        "id",
        "delivery_id",
        "operation_state"
      ],
      "title": "DeliveryOperationObservation",
      "type": "object"
    }
    ```
