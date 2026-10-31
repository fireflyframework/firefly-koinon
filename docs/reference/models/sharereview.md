<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ShareReview

[All wire models](index.md)

Model aliases: `ShareReview`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `revision` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `message_count` | `integer` | Yes | Not specified |
| `source_count` | `integer` | Yes | Not specified |
| `messages` | Array of [`ConversationMessage`](conversationmessage.md) | Yes | Not specified |
| `sources` | Array of [`SourceReference`](sourcereference.md) | Yes | Not specified |
| `source_manifest_complete` | `boolean` | Yes | Not specified |
| `remembered_context_present` | `boolean` | No | `false` |
| `recipient_policy` | `string` | No | `"organization_current_acl"` |
| `omissions` | Array of `string` | No | `[]` |
| `expires_at` | `string` | Yes | Not specified |
| `identity` | [`ConversationIdentity`](conversationidentity.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### revision

- Pattern: `"^[a-f0-9]{64}$"`

### recipient_policy

- Exact value: `"organization_current_acl"`

### expires_at

- Format: `"date-time"`


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
        "revision": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Revision",
          "type": "string"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "message_count": {
          "title": "Message Count",
          "type": "integer"
        },
        "source_count": {
          "title": "Source Count",
          "type": "integer"
        },
        "messages": {
          "items": {
            "$ref": "#/$defs/ConversationMessage"
          },
          "title": "Messages",
          "type": "array"
        },
        "sources": {
          "items": {
            "$ref": "#/$defs/SourceReference"
          },
          "title": "Sources",
          "type": "array"
        },
        "source_manifest_complete": {
          "title": "Source Manifest Complete",
          "type": "boolean"
        },
        "remembered_context_present": {
          "default": false,
          "title": "Remembered Context Present",
          "type": "boolean"
        },
        "recipient_policy": {
          "const": "organization_current_acl",
          "default": "organization_current_acl",
          "title": "Recipient Policy",
          "type": "string"
        },
        "omissions": {
          "default": [],
          "items": {
            "type": "string"
          },
          "title": "Omissions",
          "type": "array"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        },
        "identity": {
          "anyOf": [
            {
              "$ref": "#/$defs/ConversationIdentity"
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
        "revision",
        "title",
        "message_count",
        "source_count",
        "messages",
        "sources",
        "source_manifest_complete",
        "expires_at"
      ],
      "title": "ShareReview",
      "type": "object"
    }
    ```
