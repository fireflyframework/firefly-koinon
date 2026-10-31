<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExportReview

[All wire models](index.md)

Model aliases: `ExportReview`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `revision` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `format` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `message_count` | `integer` | Yes | Not specified |
| `source_count` | `integer` | Yes | Not specified |
| `row_count` | `integer` or `null` | No | `null` |
| `row_cap` | `integer` or `null` | No | `null` |
| `truncated` | `boolean` or `null` | No | `null` |
| `completeness` | `string` | Yes | Not specified |
| `messages` | Array of [`ConversationMessage`](conversationmessage.md) | No | `[]` |
| `sources` | Array of [`SourceReference`](sourcereference.md) | No | `[]` |
| `source_manifest_complete` | `boolean` | No | `false` |
| `result` | [`StoredResult`](storedresult.md) or `null` | No | `null` |
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

### kind

- Allowed values: `"conversation"`, `"query_result"`

### format

- Allowed values: `"markdown"`, `"json"`, `"parquet"`, `"csv"`, `"jsonl"`

### message_count

- Minimum: `0`
- Maximum: `200`

### source_count

- Minimum: `0`
- Maximum: `500`

### row_count

- anyOf branch 1 (`integer`): Minimum: `0`

### row_cap

- anyOf branch 1 (`integer`): Minimum: `1`

### completeness

- Allowed values: `"selected_messages"`, `"bounded"`, `"unknown"`

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
        "kind": {
          "enum": [
            "conversation",
            "query_result"
          ],
          "title": "Kind",
          "type": "string"
        },
        "format": {
          "enum": [
            "markdown",
            "json",
            "parquet",
            "csv",
            "jsonl"
          ],
          "title": "Format",
          "type": "string"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "message_count": {
          "maximum": 200,
          "minimum": 0,
          "title": "Message Count",
          "type": "integer"
        },
        "source_count": {
          "maximum": 500,
          "minimum": 0,
          "title": "Source Count",
          "type": "integer"
        },
        "row_count": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Row Count"
        },
        "row_cap": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Row Cap"
        },
        "truncated": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Truncated"
        },
        "completeness": {
          "enum": [
            "selected_messages",
            "bounded",
            "unknown"
          ],
          "title": "Completeness",
          "type": "string"
        },
        "messages": {
          "default": [],
          "items": {
            "$ref": "#/$defs/ConversationMessage"
          },
          "title": "Messages",
          "type": "array"
        },
        "sources": {
          "default": [],
          "items": {
            "$ref": "#/$defs/SourceReference"
          },
          "title": "Sources",
          "type": "array"
        },
        "source_manifest_complete": {
          "default": false,
          "title": "Source Manifest Complete",
          "type": "boolean"
        },
        "result": {
          "anyOf": [
            {
              "$ref": "#/$defs/StoredResult"
            },
            {
              "type": "null"
            }
          ],
          "default": null
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
        "kind",
        "format",
        "title",
        "message_count",
        "source_count",
        "completeness",
        "expires_at"
      ],
      "title": "ExportReview",
      "type": "object"
    }
    ```
