<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# LineageEdge

[All wire models](index.md)

Model aliases: `LineageEdge`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `source` | `string` | Yes | Not specified |
| `target` | `string` | Yes | Not specified |
| `label` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "source": {
          "title": "Source",
          "type": "string"
        },
        "target": {
          "title": "Target",
          "type": "string"
        },
        "label": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Label"
        }
      },
      "required": [
        "source",
        "target"
      ],
      "title": "LineageEdge",
      "type": "object"
    }
    ```
