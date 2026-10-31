<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ResultColumn

[All wire models](index.md)

Model aliases: `ResultColumn`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Not specified |
| `data_type` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### name

- Minimum length: `1`
- Maximum length: `512`

### data_type

- Minimum length: `1`
- Maximum length: `255`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "name": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "data_type": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Data Type",
          "type": "string"
        }
      },
      "required": [
        "name",
        "data_type"
      ],
      "title": "ResultColumn",
      "type": "object"
    }
    ```
