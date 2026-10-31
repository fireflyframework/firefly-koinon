<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ChatRun

[All wire models](index.md)

Model aliases: `ChatRun`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `event_cursor` | `string` or `null` | No | `null` |
| `run_id` | `string` | Yes | Not specified |
| `message_id` | `string` | Yes | Not specified |
| `status` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- anyOf branch 1 (`string`): Allowed values: `"queued"`, `"running"`, `"completed"`, `"failed"`, `"cancelled"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "event_cursor": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Event Cursor"
        },
        "run_id": {
          "title": "Run Id",
          "type": "string"
        },
        "message_id": {
          "title": "Message Id",
          "type": "string"
        },
        "status": {
          "anyOf": [
            {
              "enum": [
                "queued",
                "running",
                "completed",
                "failed",
                "cancelled"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Status"
        }
      },
      "required": [
        "run_id",
        "message_id"
      ],
      "title": "ChatRun",
      "type": "object"
    }
    ```
