<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ConversationMessage

[All wire models](index.md)

Model aliases: `ConversationMessage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `role` | `string` | Yes | Not specified |
| `text` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `revision` | `string` | Yes | Not specified |
| `private_derived` | `boolean` | No | `false` |
| `source_ids` | Array of `string` | No | `[]` |
| `result_ids` | Array of `string` | No | `[]` |
| `created_at` | `string` or `null` | No | `null` |
| `presentation` | [`EvidencePresentation`](evidencepresentation.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### role

- Allowed values: `"user"`, `"assistant"`

### text

- Maximum length: `1000000`

### status

- Allowed values: `"completed"`, `"failed"`, `"cancelled"`

### revision

- Pattern: `"^[a-f0-9]{64}$"`

### source_ids

- Maximum items: `500`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`

### result_ids

- Maximum items: `100`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`

### created_at

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
        "role": {
          "enum": [
            "user",
            "assistant"
          ],
          "title": "Role",
          "type": "string"
        },
        "text": {
          "maxLength": 1000000,
          "title": "Text",
          "type": "string"
        },
        "status": {
          "enum": [
            "completed",
            "failed",
            "cancelled"
          ],
          "title": "Status",
          "type": "string"
        },
        "revision": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Revision",
          "type": "string"
        },
        "private_derived": {
          "default": false,
          "title": "Private Derived",
          "type": "boolean"
        },
        "source_ids": {
          "default": [],
          "items": {
            "maxLength": 64,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 500,
          "title": "Source Ids",
          "type": "array"
        },
        "result_ids": {
          "default": [],
          "items": {
            "maxLength": 64,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 100,
          "title": "Result Ids",
          "type": "array"
        },
        "created_at": {
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
          "title": "Created At"
        },
        "presentation": {
          "anyOf": [
            {
              "$ref": "#/$defs/EvidencePresentation"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "id",
        "role",
        "text",
        "status",
        "revision"
      ],
      "title": "ConversationMessage",
      "type": "object"
    }
    ```
