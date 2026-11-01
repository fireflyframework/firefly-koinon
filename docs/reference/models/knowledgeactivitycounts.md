<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeActivityCounts

[All wire models](index.md)

Model aliases: `KnowledgeActivityCounts`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `created` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `updated` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `consulted` | [`ObservedCount`](observedcount.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "created": {
          "$ref": "#/$defs/ObservedCount"
        },
        "updated": {
          "$ref": "#/$defs/ObservedCount"
        },
        "consulted": {
          "$ref": "#/$defs/ObservedCount"
        }
      },
      "required": [
        "created",
        "updated",
        "consulted"
      ],
      "title": "KnowledgeActivityCounts",
      "type": "object"
    }
    ```
