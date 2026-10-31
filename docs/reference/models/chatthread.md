<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ChatThread

[All wire models](index.md)

Model aliases: `ChatThread`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `revision` | `integer` | Yes | Not specified |
| `title_source` | `string` | Yes | Not specified |
| `folder_id` | `string` or `null` | Yes | Not specified |
| `archived_at` | `string` or `null` | Yes | Not specified |
| `id` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `scope` | [`KnowledgeScope`](knowledgescope.md) | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### title_source

- Allowed values: `"default"`, `"manual"`, `"ai"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "revision": {
          "title": "Revision",
          "type": "integer"
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
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Archived At"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "scope": {
          "$ref": "#/$defs/KnowledgeScope"
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
        "revision",
        "title_source",
        "folder_id",
        "archived_at",
        "id",
        "title",
        "scope",
        "created_at",
        "updated_at"
      ],
      "title": "ChatThread",
      "type": "object"
    }
    ```
