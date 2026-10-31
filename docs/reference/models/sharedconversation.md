<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SharedConversation

[All wire models](index.md)

Model aliases: `SharedConversation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `share` | [`Share`](share.md) | Yes | Not specified |
| `messages` | Array of [`ConversationMessage`](conversationmessage.md) | Yes | Not specified |
| `sources` | Array of [`SourceReference`](sourcereference.md) | Yes | Not specified |
| `source_manifest_complete` | `boolean` | Yes | Not specified |
| `identity` | [`ConversationIdentity`](conversationidentity.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "share": {
          "$ref": "#/$defs/Share"
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
        "share",
        "messages",
        "sources",
        "source_manifest_complete"
      ],
      "title": "SharedConversation",
      "type": "object"
    }
    ```
