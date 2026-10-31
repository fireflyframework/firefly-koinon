<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ChatMessage

[All wire models](index.md)

Model aliases: `ChatMessage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tool_activities` | Array of [`ToolActivity`](toolactivity.md) or `null` | No | `null` |
| `tool_activity_count` | `integer` or `null` | No | `null` |
| `tool_activity_has_more` | `boolean` or `null` | No | `null` |
| `attachments` | Array of [`AttachmentHistorySummary`](attachmenthistorysummary.md) | No | Not specified |
| `answer_policy` | [`AnswerPolicy`](answerpolicy.md) or `null` | No | `null` |
| `presentation` | [`Presentation`](presentation.md) | No | Not specified |
| `event_cursor` | `string` or `null` | No | `null` |
| `id` | `string` | Yes | Not specified |
| `run_id` | `string` or `null` | No | `null` |
| `role` | `string` | Yes | Not specified |
| `text` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `citations` | Array of [`Citation`](citation.md) | Yes | Not specified |
| `artifacts` | Array of [`OpenUIArtifact`](openuiartifact.md) | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### role

- Allowed values: `"user"`, `"assistant"`

### status

- Allowed values: `"queued"`, `"running"`, `"completed"`, `"failed"`, `"cancelled"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "tool_activities": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/ToolActivity"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Tool Activities"
        },
        "tool_activity_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Tool Activity Count"
        },
        "tool_activity_has_more": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Tool Activity Has More"
        },
        "attachments": {
          "items": {
            "$ref": "#/$defs/AttachmentHistorySummary"
          },
          "title": "Attachments",
          "type": "array"
        },
        "answer_policy": {
          "anyOf": [
            {
              "$ref": "#/$defs/AnswerPolicy"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "presentation": {
          "$ref": "#/$defs/Presentation"
        },
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
        "id": {
          "title": "Id",
          "type": "string"
        },
        "run_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "role": {
          "enum": [
            "user",
            "assistant"
          ],
          "title": "Role",
          "type": "string"
        },
        "text": {
          "title": "Text",
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
        "citations": {
          "items": {
            "$ref": "#/$defs/Citation"
          },
          "title": "Citations",
          "type": "array"
        },
        "artifacts": {
          "items": {
            "$ref": "#/$defs/OpenUIArtifact"
          },
          "title": "Artifacts",
          "type": "array"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "role",
        "text",
        "status",
        "citations",
        "artifacts",
        "created_at"
      ],
      "title": "ChatMessage",
      "type": "object"
    }
    ```
