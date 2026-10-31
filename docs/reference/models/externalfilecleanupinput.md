<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalFileCleanupInput

[All wire models](index.md)

Model aliases: `ExternalFileCleanupInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `review_ids` | Array of `string` | Yes | Not specified |
| `max_objects` | `integer` | No | `32` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### review_ids

- Minimum items: `1`
- Maximum items: `25`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`

### max_objects

- Minimum: `1`
- Maximum: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "review_ids": {
          "items": {
            "maxLength": 64,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 25,
          "minItems": 1,
          "title": "Review Ids",
          "type": "array"
        },
        "max_objects": {
          "default": 32,
          "maximum": 64,
          "minimum": 1,
          "title": "Max Objects",
          "type": "integer"
        }
      },
      "required": [
        "review_ids"
      ],
      "title": "ExternalFileCleanupInput",
      "type": "object"
    }
    ```
