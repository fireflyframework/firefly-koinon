<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# StructuredKnowledgeCapabilities

[All wire models](index.md)

Model aliases: `StructuredKnowledgeCapabilities`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `bounds` | [`StructuredKnowledgeBounds`](structuredknowledgebounds.md) | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "bounds": {
          "$ref": "#/$defs/StructuredKnowledgeBounds"
        }
      },
      "required": [
        "bounds"
      ],
      "title": "StructuredKnowledgeCapabilities",
      "type": "object"
    }
    ```
