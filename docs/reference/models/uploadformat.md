<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# UploadFormat

[All wire models](index.md)

Model aliases: `UploadFormat`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `mode` | `string` | Yes | Not specified |
| `extensions` | Array of `string` | Yes | Not specified |
| `available` | `boolean` | Yes | Not specified |
| `reason` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### mode

- Allowed values: `"document"`, `"dataset"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "mode": {
          "enum": [
            "document",
            "dataset"
          ],
          "title": "Mode",
          "type": "string"
        },
        "extensions": {
          "items": {
            "type": "string"
          },
          "title": "Extensions",
          "type": "array"
        },
        "available": {
          "title": "Available",
          "type": "boolean"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason"
        }
      },
      "required": [
        "mode",
        "extensions",
        "available"
      ],
      "title": "UploadFormat",
      "type": "object"
    }
    ```
