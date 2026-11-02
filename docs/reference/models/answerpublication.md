<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AnswerPublication

[All wire models](index.md)

Model aliases: `AnswerPublication`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `format` | `string` | Yes | Not specified |
| `chunk_size` | `integer` | Yes | Not specified |
| `chunk_count` | `integer` | Yes | Not specified |
| `text_sha256` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### format

- Exact value: `"verified-unicode-v1"`

### chunk_size

- Exact value: `128`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "format": {
          "const": "verified-unicode-v1",
          "title": "Format",
          "type": "string"
        },
        "chunk_size": {
          "const": 128,
          "title": "Chunk Size",
          "type": "integer"
        },
        "chunk_count": {
          "title": "Chunk Count",
          "type": "integer"
        },
        "text_sha256": {
          "title": "Text Sha256",
          "type": "string"
        }
      },
      "required": [
        "format",
        "chunk_size",
        "chunk_count",
        "text_sha256"
      ],
      "title": "AnswerPublication",
      "type": "object"
    }
    ```
