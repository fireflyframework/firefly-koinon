<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentObservation

[All wire models](index.md)

Model aliases: `AttachmentObservation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `available` | `boolean` or `null` | Yes | Not specified |
| `reason` | `string` | Yes | Not specified |
| `configured` | `boolean` | No | `false` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "available": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "title": "Available"
        },
        "reason": {
          "title": "Reason",
          "type": "string"
        },
        "configured": {
          "default": false,
          "title": "Configured",
          "type": "boolean"
        }
      },
      "required": [
        "available",
        "reason"
      ],
      "title": "AttachmentObservation",
      "type": "object"
    }
    ```
