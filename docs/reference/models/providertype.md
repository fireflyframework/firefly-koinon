<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProviderType

[All wire models](index.md)

Model aliases: `ProviderType`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `fields` | Array of [`FieldSchema`](fieldschema.md) | Yes | Not specified |

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
        "name": {
          "title": "Name",
          "type": "string"
        },
        "fields": {
          "items": {
            "$ref": "#/$defs/FieldSchema"
          },
          "title": "Fields",
          "type": "array"
        }
      },
      "required": [
        "id",
        "name",
        "fields"
      ],
      "title": "ProviderType",
      "type": "object"
    }
    ```
