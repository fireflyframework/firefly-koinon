<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ConversationSnapshot

[All wire models](index.md)

Model aliases: `ConversationSnapshot`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `thread_id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `owner_subject` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `revision` | `string` | Yes | Not specified |
| `messages` | Array of [`ConversationMessage`](conversationmessage.md) | Yes | Not specified |
| `sources` | Array of [`SourceReference`](sourcereference.md) | No | `[]` |
| `source_manifest_complete` | `boolean` | No | `false` |
| `originating_token_ids` | Array of `string` | No | `[]` |
| `identity` | [`ConversationIdentity`](conversationidentity.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### thread_id

- Minimum length: `1`
- Maximum length: `64`

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### owner_subject

- Minimum length: `1`
- Maximum length: `512`

### title

- Minimum length: `1`
- Maximum length: `160`

### revision

- Pattern: `"^[a-f0-9]{64}$"`

### messages

- Minimum items: `1`
- Maximum items: `200`

### sources

- Maximum items: `500`

### originating_token_ids

- Maximum items: `200`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`

### identity

- Presentation identity recorded when the export or share review was created. Null means historical identity was not recorded; it never uses today's branding.


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "thread_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Thread Id",
          "type": "string"
        },
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "owner_subject": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Owner Subject",
          "type": "string"
        },
        "title": {
          "maxLength": 160,
          "minLength": 1,
          "title": "Title",
          "type": "string"
        },
        "revision": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Revision",
          "type": "string"
        },
        "messages": {
          "items": {
            "$ref": "#/$defs/ConversationMessage"
          },
          "maxItems": 200,
          "minItems": 1,
          "title": "Messages",
          "type": "array"
        },
        "sources": {
          "default": [],
          "items": {
            "$ref": "#/$defs/SourceReference"
          },
          "maxItems": 500,
          "title": "Sources",
          "type": "array"
        },
        "source_manifest_complete": {
          "default": false,
          "title": "Source Manifest Complete",
          "type": "boolean"
        },
        "originating_token_ids": {
          "default": [],
          "items": {
            "maxLength": 64,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 200,
          "title": "Originating Token Ids",
          "type": "array"
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
          "default": null,
          "description": "Presentation identity recorded when the export or share review was created. Null means historical identity was not recorded; it never uses today's branding."
        }
      },
      "required": [
        "thread_id",
        "tenant_id",
        "owner_subject",
        "title",
        "revision",
        "messages"
      ],
      "title": "ConversationSnapshot",
      "type": "object"
    }
    ```
