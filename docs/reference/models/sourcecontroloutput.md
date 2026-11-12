<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceControlOutput

[All wire models](index.md)

Model aliases: `SourceControlOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `operation_id` | `string` | Yes | Not specified |
| `receipt_id` | `string` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |
| `control_revision` | `integer` | Yes | Not specified |
| `run_id` | `string` or `null` | No | `null` |
| `disposition` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### receipt_id

- Minimum length: `1`
- Maximum length: `64`

### action

- Allowed values: `"sync"`, `"pause"`, `"resume"`, `"cancel"`, `"retry"`, `"retire"`

### run_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### disposition

- Allowed values: `"queued"`, `"paused"`, `"active"`, `"stopping"`, `"reconciling"`, `"retired"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "operation_id": {
          "title": "Operation Id",
          "type": "string"
        },
        "receipt_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Receipt Id",
          "type": "string"
        },
        "action": {
          "enum": [
            "sync",
            "pause",
            "resume",
            "cancel",
            "retry",
            "retire"
          ],
          "title": "Action",
          "type": "string"
        },
        "control_revision": {
          "title": "Control Revision",
          "type": "integer"
        },
        "run_id": {
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
          "default": null,
          "title": "Run Id"
        },
        "disposition": {
          "enum": [
            "queued",
            "paused",
            "active",
            "stopping",
            "reconciling",
            "retired"
          ],
          "title": "Disposition",
          "type": "string"
        }
      },
      "required": [
        "operation_id",
        "receipt_id",
        "action",
        "control_revision",
        "disposition"
      ],
      "title": "SourceControlOutput",
      "type": "object"
    }
    ```
