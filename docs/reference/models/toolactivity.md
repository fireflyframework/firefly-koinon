<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ToolActivity

[All wire models](index.md)

Model aliases: `ToolActivity`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `call_id` | `string` | Yes | Not specified |
| `tool_name` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `occurred_at` | `string` | Yes | Not specified |
| `started_at` | `string` or `null` | No | `null` |
| `finished_at` | `string` or `null` | No | `null` |
| `duration_ms` | `integer` or `null` | No | `null` |
| `summary` | `string` | Yes | Not specified |
| `result_id` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### tool_name

- Allowed values: `"search_knowledge"`, `"inspect_schema"`, `"query_dataset"`, `"search_private_attachments"`, `"propose_catalog_update"`

### status

- Allowed values: `"queued"`, `"running"`, `"completed"`, `"failed"`, `"cancelled"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "call_id": {
          "title": "Call Id",
          "type": "string"
        },
        "tool_name": {
          "enum": [
            "search_knowledge",
            "inspect_schema",
            "query_dataset",
            "search_private_attachments",
            "propose_catalog_update"
          ],
          "title": "Tool Name",
          "type": "string"
        },
        "status": {
          "enum": [
            "queued",
            "running",
            "completed",
            "failed",
            "cancelled"
          ],
          "title": "Status",
          "type": "string"
        },
        "occurred_at": {
          "title": "Occurred At",
          "type": "string"
        },
        "started_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Started At"
        },
        "finished_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Finished At"
        },
        "duration_ms": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Duration Ms"
        },
        "summary": {
          "title": "Summary",
          "type": "string"
        },
        "result_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Result Id"
        }
      },
      "required": [
        "call_id",
        "tool_name",
        "status",
        "occurred_at",
        "summary"
      ],
      "title": "ToolActivity",
      "type": "object"
    }
    ```
