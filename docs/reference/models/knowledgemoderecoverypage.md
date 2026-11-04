<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeModeRecoveryPage

[All wire models](index.md)

Model aliases: `KnowledgeModeRecoveryPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`KnowledgeModeRecoveryReceipt`](knowledgemoderecoveryreceipt.md) | Yes | Not specified |
| `next_cursor` | `string` or `null` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "items": {
          "items": {
            "$ref": "#/$defs/KnowledgeModeRecoveryReceipt"
          },
          "title": "Items",
          "type": "array"
        },
        "next_cursor": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Next Cursor"
        }
      },
      "required": [
        "items",
        "next_cursor"
      ],
      "title": "KnowledgeModeRecoveryPage",
      "type": "object"
    }
    ```
