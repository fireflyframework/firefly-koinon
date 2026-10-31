<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# TokenScope

[All wire models](index.md)

Model aliases: `TokenScope`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `dependencies` | Array of `string` | Yes | Not specified |

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
        "dependencies": {
          "items": {
            "type": "string"
          },
          "title": "Dependencies",
          "type": "array"
        }
      },
      "required": [
        "id",
        "name",
        "dependencies"
      ],
      "title": "TokenScope",
      "type": "object"
    }
    ```
