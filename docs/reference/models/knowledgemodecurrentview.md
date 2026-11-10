<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeModeCurrentView

[All wire models](index.md)

Model aliases: `KnowledgeModeCurrentView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `transition` | [`KnowledgeModeTransitionView`](knowledgemodetransitionview.md) or `null` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "transition": {
          "anyOf": [
            {
              "$ref": "#/$defs/KnowledgeModeTransitionView"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "transition"
      ],
      "title": "KnowledgeModeCurrentView",
      "type": "object"
    }
    ```
