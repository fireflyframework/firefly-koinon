<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Export

[All wire models](index.md)

Model aliases: `Export`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `format` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `revision` | `string` | Yes | Not specified |
| `completeness` | `string` | Yes | Not specified |
| `row_count` | `integer` or `null` | No | `null` |
| `truncated` | `boolean` or `null` | No | `null` |
| `created_at` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### kind

- Allowed values: `"conversation"`, `"query_result"`

### format

- Allowed values: `"markdown"`, `"json"`, `"parquet"`, `"csv"`, `"jsonl"`

### status

- Allowed values: `"ready"`, `"cancelled"`, `"expired"`

### revision

- Pattern: `"^[a-f0-9]{64}$"`

### completeness

- Allowed values: `"selected_messages"`, `"bounded"`, `"unknown"`

### created_at

- Format: `"date-time"`

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
        "status": {
          "enum": [
            "ready",
            "cancelled",
            "expired"
          ],
          "title": "Status",
          "type": "string"
        },
        "revision": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Revision",
          "type": "string"
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
        "row_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Row Count"
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
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "kind",
        "format",
        "title",
        "status",
        "revision",
        "completeness",
        "created_at",
        "expires_at"
      ],
      "title": "Export",
      "type": "object"
    }
    ```
