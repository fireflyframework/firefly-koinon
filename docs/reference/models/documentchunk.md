<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentChunk

[All wire models](index.md)

Model aliases: `DocumentChunk`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `index` | `integer` | Yes | Not specified |
| `total_chunks` | `integer` | Yes | Not specified |
| `text` | `string` | Yes | Not specified |
| `char_start` | `integer` | Yes | Not specified |
| `char_end` | `integer` | Yes | Not specified |
| `page` | `integer` or `null` | No | `null` |
| `section_path` | `string` or `null` | No | `null` |
| `embedding_model` | `string` or `null` | No | `null` |

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
        "index": {
          "title": "Index",
          "type": "integer"
        },
        "total_chunks": {
          "title": "Total Chunks",
          "type": "integer"
        },
        "text": {
          "title": "Text",
          "type": "string"
        },
        "char_start": {
          "title": "Char Start",
          "type": "integer"
        },
        "char_end": {
          "title": "Char End",
          "type": "integer"
        },
        "page": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page"
        },
        "section_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Section Path"
        },
        "embedding_model": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Embedding Model"
        }
      },
      "required": [
        "id",
        "index",
        "total_chunks",
        "text",
        "char_start",
        "char_end"
      ],
      "title": "DocumentChunk",
      "type": "object"
    }
    ```
