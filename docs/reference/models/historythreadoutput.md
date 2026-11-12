<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# HistoryThreadOutput

[All wire models](index.md)

Model aliases: `HistoryThreadOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `title_source` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `folder_id` | `string` or `null` | Yes | Not specified |
| `archived_at` | `string` or `null` | Yes | Not specified |
| `scope` | [`KnowledgeScope`](knowledgescope.md) | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### title_source

- Allowed values: `"default"`, `"manual"`, `"ai"`

### archived_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### created_at

- Format: `"date-time"`

### updated_at

- Format: `"date-time"`


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
        "title": {
          "title": "Title",
          "type": "string"
        },
        "title_source": {
          "enum": [
            "default",
            "manual",
            "ai"
          ],
          "title": "Title Source",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "folder_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Folder Id"
        },
        "archived_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Archived At"
        },
        "scope": {
          "$ref": "#/$defs/KnowledgeScope"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "updated_at": {
          "format": "date-time",
          "title": "Updated At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "title",
        "title_source",
        "revision",
        "folder_id",
        "archived_at",
        "scope",
        "created_at",
        "updated_at"
      ],
      "title": "HistoryThreadOutput",
      "type": "object"
    }
    ```
