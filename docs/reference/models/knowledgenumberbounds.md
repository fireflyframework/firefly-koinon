<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeNumberBounds

[All wire models](index.md)

Model aliases: `KnowledgeNumberBounds`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `minimum` | `number` | Yes | Not specified |
| `maximum` | `number` | Yes | Not specified |

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
          "type": "number"
        },
        "maximum": {
          "title": "Maximum",
          "type": "number"
        }
      },
      "required": [
        "minimum",
        "maximum"
      ],
      "title": "KnowledgeNumberBounds",
      "type": "object"
    }
    ```
