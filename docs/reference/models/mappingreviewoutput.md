<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MappingReviewOutput

[All wire models](index.md)

Model aliases: `MappingReviewOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `status` | `string` | No | `"reviewed"` |
| `expires_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Exact value: `"reviewed"`

### expires_at

- Format: `"date-time"`


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
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "status": {
          "const": "reviewed",
          "default": "reviewed",
          "title": "Status",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "revision",
        "expires_at"
      ],
      "title": "MappingReviewOutput",
      "type": "object"
    }
    ```
