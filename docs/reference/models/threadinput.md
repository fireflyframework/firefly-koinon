<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ThreadInput

[All wire models](index.md)

Model aliases: `ThreadInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `folder_id` | `string` or `null` | No | `null` |
| `title` | `string` | No | `"New conversation"` |
| `scope` | [`KnowledgeScope`](knowledgescope.md) or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "folder_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Folder Id"
        },
        "title": {
          "default": "New conversation",
          "title": "Title",
          "type": "string"
        },
        "scope": {
          "anyOf": [
            {
              "$ref": "#/$defs/KnowledgeScope"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "title": "ThreadInput",
      "type": "object"
    }
    ```
