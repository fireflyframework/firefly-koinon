<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Lineage

[All wire models](index.md)

Model aliases: `Lineage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `nodes` | Array of [`LineageNode`](lineagenode.md) | Yes | Not specified |
| `edges` | Array of [`LineageEdge`](lineageedge.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "nodes": {
          "items": {
            "$ref": "#/$defs/LineageNode"
          },
          "title": "Nodes",
          "type": "array"
        },
        "edges": {
          "items": {
            "$ref": "#/$defs/LineageEdge"
          },
          "title": "Edges",
          "type": "array"
        }
      },
      "required": [
        "nodes",
        "edges"
      ],
      "title": "Lineage",
      "type": "object"
    }
    ```
