<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# PrivateChunkView

[All wire models](index.md)

Model aliases: `PrivateChunkView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `attachment_id` | `string` | Yes | Not specified |
| `index` | `integer` | Yes | Not specified |
| `text` | `string` | Yes | Not specified |
| `page` | `integer` or `null` | No | `null` |
| `section_path` | Array of `string` | Yes | Not specified |
| `char_start` | `integer` | Yes | Not specified |
| `char_end` | `integer` | Yes | Not specified |
| `offset_basis` | `string` | No | `"normalized_text_code_points"` |
| `sha256` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### offset_basis

- Exact value: `"normalized_text_code_points"`


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
        "attachment_id": {
          "title": "Attachment Id",
          "type": "string"
        },
        "index": {
          "title": "Index",
          "type": "integer"
        },
        "text": {
          "title": "Text",
          "type": "string"
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
          "items": {
            "type": "string"
          },
          "title": "Section Path",
          "type": "array"
        },
        "char_start": {
          "title": "Char Start",
          "type": "integer"
        },
        "char_end": {
          "title": "Char End",
          "type": "integer"
        },
        "offset_basis": {
          "const": "normalized_text_code_points",
          "default": "normalized_text_code_points",
          "title": "Offset Basis",
          "type": "string"
        },
        "sha256": {
          "title": "Sha256",
          "type": "string"
        }
      },
      "required": [
        "id",
        "attachment_id",
        "index",
        "text",
        "section_path",
        "char_start",
        "char_end",
        "sha256"
      ],
      "title": "PrivateChunkView",
      "type": "object"
    }
    ```
