<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeIntegerBounds

[All wire models](index.md)

Model aliases: `KnowledgeIntegerBounds`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `minimum` | `integer` | Yes | Not specified |
| `maximum` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "minimum": {
          "title": "Minimum",
          "type": "integer"
        },
        "maximum": {
          "title": "Maximum",
          "type": "integer"
        }
      },
      "required": [
        "minimum",
        "maximum"
      ],
      "title": "KnowledgeIntegerBounds",
      "type": "object"
    }
    ```
