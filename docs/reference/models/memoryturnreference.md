<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MemoryTurnReference

[All wire models](index.md)

Model aliases: `MemoryTurnReference`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `run_id` | `string` | Yes | Not specified |
| `generation_id` | `string` or `null` | No | `null` |
| `thread_id` | `string` | Yes | Not specified |
| `conversation_title` | `string` | Yes | Not specified |
| `user_created_at` | `string` | Yes | Not specified |
| `user_message_id` | `string` | Yes | Not specified |
| `user_sha256` | `string` | Yes | Not specified |
| `answer_message_id` | `string` | Yes | Not specified |
| `answer_sha256` | `string` | Yes | Not specified |
| `answer_included` | `boolean` | No | `false` |
| `availability` | `string` | No | `"available"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### run_id

- Minimum length: `1`
- Maximum length: `64`

### generation_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### thread_id

- Minimum length: `1`
- Maximum length: `64`

### conversation_title

- Minimum length: `1`
- Maximum length: `160`

### user_created_at

- Format: `"date-time"`

### user_message_id

- Minimum length: `1`
- Maximum length: `64`

### user_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### answer_message_id

- Minimum length: `1`
- Maximum length: `64`

### answer_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### availability

- Allowed values: `"available"`, `"archived"`, `"deleted"`, `"moved"`, `"memory_disabled"`, `"changed"`, `"unverified"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "run_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Run Id",
          "type": "string"
        },
        "generation_id": {
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
          "title": "Generation Id"
        },
        "thread_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Thread Id",
          "type": "string"
        },
        "conversation_title": {
          "maxLength": 160,
          "minLength": 1,
          "title": "Conversation Title",
          "type": "string"
        },
        "user_created_at": {
          "format": "date-time",
          "title": "User Created At",
          "type": "string"
        },
        "user_message_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "User Message Id",
          "type": "string"
        },
        "user_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "User Sha256",
          "type": "string"
        },
        "answer_message_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Answer Message Id",
          "type": "string"
        },
        "answer_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Answer Sha256",
          "type": "string"
        },
        "answer_included": {
          "default": false,
          "title": "Answer Included",
          "type": "boolean"
        },
        "availability": {
          "default": "available",
          "enum": [
            "available",
            "archived",
            "deleted",
            "moved",
            "memory_disabled",
            "changed",
            "unverified"
          ],
          "title": "Availability",
          "type": "string"
        }
      },
      "required": [
        "run_id",
        "thread_id",
        "conversation_title",
        "user_created_at",
        "user_message_id",
        "user_sha256",
        "answer_message_id",
        "answer_sha256"
      ],
      "title": "MemoryTurnReference",
      "type": "object"
    }
    ```
