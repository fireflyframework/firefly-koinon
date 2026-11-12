<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceRunOutput

[All wire models](index.md)

Model aliases: `SourceRunOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `mapping_id` | `string` | Yes | Not specified |
| `policy_revision` | `integer` | Yes | Not specified |
| `control_revision` | `integer` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `stopping` | `boolean` | Yes | Not specified |
| `retry_of_run_id` | `string` or `null` | Yes | Not specified |
| `counters` | Map of string keys to `integer` | Yes | Not specified |
| `enumeration_complete` | `boolean` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `finished_at` | `string` or `null` | Yes | Not specified |
| `can_cancel` | `boolean` | Yes | Not specified |
| `can_retry` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### mapping_id

- Minimum length: `1`
- Maximum length: `64`

### status

- Allowed values: `"queued"`, `"running"`, `"reconciling"`, `"reconnect_required"`, `"succeeded"`, `"partial"`, `"failed"`, `"cancelled"`

### retry_of_run_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### counters

- Additional properties: `integer`

### created_at

- Format: `"date-time"`

### finished_at

- anyOf branch 1 (`string`): Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "mapping_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Mapping Id",
          "type": "string"
        },
        "policy_revision": {
          "title": "Policy Revision",
          "type": "integer"
        },
        "control_revision": {
          "title": "Control Revision",
          "type": "integer"
        },
        "status": {
          "enum": [
            "queued",
            "running",
            "reconciling",
            "reconnect_required",
            "succeeded",
            "partial",
            "failed",
            "cancelled"
          ],
          "title": "Status",
          "type": "string"
        },
        "stopping": {
          "title": "Stopping",
          "type": "boolean"
        },
        "retry_of_run_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Retry Of Run Id"
        },
        "counters": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Counters",
          "type": "object"
        },
        "enumeration_complete": {
          "title": "Enumeration Complete",
          "type": "boolean"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "finished_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Finished At"
        },
        "can_cancel": {
          "title": "Can Cancel",
          "type": "boolean"
        },
        "can_retry": {
          "title": "Can Retry",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "mapping_id",
        "policy_revision",
        "control_revision",
        "status",
        "stopping",
        "retry_of_run_id",
        "counters",
        "enumeration_complete",
        "created_at",
        "finished_at",
        "can_cancel",
        "can_retry"
      ],
      "title": "SourceRunOutput",
      "type": "object"
    }
    ```
