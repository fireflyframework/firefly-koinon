<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GlossaryTermCreate

[All wire models](index.md)

Model aliases: `GlossaryTermCreate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `term` | `string` | Yes | Not specified |
| `definition` | `string` | Yes | Not specified |
| `synonyms` | Array of `string` | No | Not specified |
| `tags` | Array of `string` | No | Not specified |
| `related_columns` | Array of `string` | No | Not specified |
| `related_metrics` | Array of `string` | No | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### term

- Minimum length: `1`
- Maximum length: `512`

### definition

- Minimum length: `1`
- Maximum length: `16000`

### synonyms

- Maximum items: `64`
- Each item: Maximum length: `512`

### tags

- Maximum items: `64`
- Each item: Maximum length: `512`

### related_columns

- Maximum items: `64`
- Each item: Maximum length: `512`

### related_metrics

- Maximum items: `64`
- Each item: Maximum length: `512`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "term": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Term",
          "type": "string"
        },
        "definition": {
          "maxLength": 16000,
          "minLength": 1,
          "title": "Definition",
          "type": "string"
        },
        "synonyms": {
          "items": {
            "maxLength": 512,
            "type": "string"
          },
          "maxItems": 64,
          "title": "Synonyms",
          "type": "array"
        },
        "tags": {
          "items": {
            "maxLength": 512,
            "type": "string"
          },
          "maxItems": 64,
          "title": "Tags",
          "type": "array"
        },
        "related_columns": {
          "items": {
            "maxLength": 512,
            "type": "string"
          },
          "maxItems": 64,
          "title": "Related Columns",
          "type": "array"
        },
        "related_metrics": {
          "items": {
            "maxLength": 512,
            "type": "string"
          },
          "maxItems": 64,
          "title": "Related Metrics",
          "type": "array"
        }
      },
      "required": [
        "term",
        "definition"
      ],
      "title": "GlossaryTermCreate",
      "type": "object"
    }
    ```
