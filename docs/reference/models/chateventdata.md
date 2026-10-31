<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ChatEventData

[All wire models](index.md)

Model aliases: `ChatEventData`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `proposal_update` | [`ProposalUpdate`](proposalupdate.md) or `null` | No | `null` |
| `tool_activity` | [`ToolActivity`](toolactivity.md) or `null` | No | `null` |
| `answer_policy` | [`AnswerPolicy`](answerpolicy.md) or `null` | No | `null` |
| `presentation` | [`Presentation`](presentation.md) or `null` | No | `null` |
| `text` | `string` or `null` | No | `null` |
| `stage` | `string` or `null` | No | `null` |
| `message` | `string` or `null` | No | `null` |
| `status` | `string` or `null` | No | `null` |
| `code` | `string` or `null` | No | `null` |
| `message_id` | `string` or `null` | No | `null` |
| `artifact` | [`OpenUIArtifact`](openuiartifact.md) or `null` | No | `null` |
| `citation` | [`Citation`](citation.md) or `null` | No | `null` |

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
        "proposal_update": {
          "anyOf": [
            {
              "$ref": "#/$defs/ProposalUpdate"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "tool_activity": {
          "anyOf": [
            {
              "$ref": "#/$defs/ToolActivity"
            },
            {
              "type": "null"
            }
          ],
          "default": null
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
          "anyOf": [
            {
              "$ref": "#/$defs/Presentation"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "text": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Text"
        },
        "stage": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stage"
        },
        "message": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Message"
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
        },
        "code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Code"
        },
        "message_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Message Id"
        },
        "artifact": {
          "anyOf": [
            {
              "$ref": "#/$defs/OpenUIArtifact"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "citation": {
          "anyOf": [
            {
              "$ref": "#/$defs/Citation"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "title": "ChatEventData",
      "type": "object"
    }
    ```
