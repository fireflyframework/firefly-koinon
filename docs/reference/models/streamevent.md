<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# StreamEvent

[All wire models](index.md)

Model aliases: `StreamEvent`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `type` | `string` | Yes | Not specified |
| `data` | [`ChatEventData`](chateventdata.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "type": {
          "title": "Type",
          "type": "string"
        },
        "data": {
          "$ref": "#/$defs/ChatEventData"
        }
      },
      "required": [
        "id",
        "type",
        "data"
      ],
      "title": "StreamEvent",
      "type": "object"
    }
    ```
