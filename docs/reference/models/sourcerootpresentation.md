<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceRootPresentation

[All wire models](index.md)

Model aliases: `SourceRootPresentation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Not specified |
| `relative_path` | Array of `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### name

- Maximum length: `4096`

### relative_path

- Maximum items: `256`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "name": {
          "maxLength": 4096,
          "title": "Name",
          "type": "string"
        },
        "relative_path": {
          "items": {
            "type": "string"
          },
          "maxItems": 256,
          "title": "Relative Path",
          "type": "array"
        }
      },
      "required": [
        "name",
        "relative_path"
      ],
      "title": "SourceRootPresentation",
      "type": "object"
    }
    ```
