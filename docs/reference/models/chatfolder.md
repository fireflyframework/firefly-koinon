<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ChatFolder

[All wire models](index.md)

Model aliases: `ChatFolder`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `parent_id` | `string` or `null` | Yes | Not specified |
| `scope` | [`KnowledgeScope`](knowledgescope.md) | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `memory_enabled` | `boolean` | No | `false` |
| `conversation_count` | `integer` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

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
        "name": {
          "title": "Name",
          "type": "string"
        },
        "parent_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Parent Id"
        },
        "scope": {
          "$ref": "#/$defs/KnowledgeScope"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "memory_enabled": {
          "default": false,
          "title": "Memory Enabled",
          "type": "boolean"
        },
        "conversation_count": {
          "title": "Conversation Count",
          "type": "integer"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "updated_at": {
          "title": "Updated At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "parent_id",
        "scope",
        "revision",
        "conversation_count",
        "created_at",
        "updated_at"
      ],
      "title": "ChatFolder",
      "type": "object"
    }
    ```
