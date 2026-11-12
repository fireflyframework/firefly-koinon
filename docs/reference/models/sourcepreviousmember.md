<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourcePreviousMember

[All wire models](index.md)

Model aliases: `SourcePreviousMember`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `table_id` | `string` | Yes | Not specified |
| `catalog_table_id` | `string` | Yes | Not specified |
| `locator` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### catalog_table_id

- Minimum length: `1`
- Maximum length: `64`

### locator

- Maximum length: `2048`

### name

- Maximum length: `255`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "table_id": {
          "title": "Table Id",
          "type": "string"
        },
        "catalog_table_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Catalog Table Id",
          "type": "string"
        },
        "locator": {
          "maxLength": 2048,
          "title": "Locator",
          "type": "string"
        },
        "name": {
          "maxLength": 255,
          "title": "Name",
          "type": "string"
        }
      },
      "required": [
        "table_id",
        "catalog_table_id",
        "locator",
        "name"
      ],
      "title": "SourcePreviousMember",
      "type": "object"
    }
    ```
