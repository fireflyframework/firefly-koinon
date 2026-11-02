<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# FileRecoveryView

[All wire models](index.md)

Model aliases: `FileRecoveryView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `batch_id` | `string` | Yes | Not specified |
| `item_id` | `string` | Yes | Not specified |
| `batch_revision` | `integer` | Yes | Not specified |
| `native_state` | `string` | Yes | Not specified |
| `operation` | `string` or `null` | Yes | Not specified |
| `reason_code` | `string` or `null` | No | `null` |
| `attempts` | `integer` | Yes | Not specified |
| `max_attempts` | `integer` | Yes | Not specified |
| `checked_at` | `string` or `null` | Yes | Not specified |
| `job_status` | `string` | Yes | Not specified |
| `original_receipt_state` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### batch_id

- Minimum length: `1`
- Maximum length: `64`

### item_id

- Minimum length: `1`
- Maximum length: `64`

### batch_revision

- Minimum: `1`
- Maximum: `2147483647`

### native_state

- Allowed values: `"absent"`, `"admitted"`, `"prepared"`, `"committed"`, `"unknown"`, `"not_checked"`

### operation

- anyOf branch 1 (`string`): Allowed values: `"retry_processing"`, `"finalize_publication"`, `"acknowledge_commit"`

### reason_code

- anyOf branch 1 (`string`): Maximum length: `64`

### attempts

- Minimum: `0`
- Maximum: `2147483647`

### max_attempts

- Minimum: `1`
- Maximum: `2147483647`

### checked_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### job_status

- Allowed values: `"queued"`, `"running"`, `"succeeded"`, `"failed"`, `"cancelled"`, `"unknown"`

### original_receipt_state

- Allowed values: `"verified"`, `"unavailable"`, `"not_checked"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "batch_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Batch Id",
          "type": "string"
        },
        "item_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Item Id",
          "type": "string"
        },
        "batch_revision": {
          "maximum": 2147483647,
          "minimum": 1,
          "title": "Batch Revision",
          "type": "integer"
        },
        "native_state": {
          "enum": [
            "absent",
            "admitted",
            "prepared",
            "committed",
            "unknown",
            "not_checked"
          ],
          "title": "Native State",
          "type": "string"
        },
        "operation": {
          "anyOf": [
            {
              "enum": [
                "retry_processing",
                "finalize_publication",
                "acknowledge_commit"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Operation"
        },
        "reason_code": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason Code"
        },
        "attempts": {
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Attempts",
          "type": "integer"
        },
        "max_attempts": {
          "maximum": 2147483647,
          "minimum": 1,
          "title": "Max Attempts",
          "type": "integer"
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
          "title": "Checked At"
        },
        "job_status": {
          "enum": [
            "queued",
            "running",
            "succeeded",
            "failed",
            "cancelled",
            "unknown"
          ],
          "title": "Job Status",
          "type": "string"
        },
        "original_receipt_state": {
          "enum": [
            "verified",
            "unavailable",
            "not_checked"
          ],
          "title": "Original Receipt State",
          "type": "string"
        }
      },
      "required": [
        "batch_id",
        "item_id",
        "batch_revision",
        "native_state",
        "operation",
        "attempts",
        "max_attempts",
        "checked_at",
        "job_status",
        "original_receipt_state"
      ],
      "title": "FileRecoveryView",
      "type": "object"
    }
    ```
