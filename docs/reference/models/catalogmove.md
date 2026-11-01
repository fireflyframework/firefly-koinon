<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CatalogMove

[All wire models](index.md)

Model aliases: `CatalogMove`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `parent_id` | `string` | Yes | Not specified |
| `expected_parent_id` | `string` | Yes | Not specified |
| `expected_updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### parent_id

- Minimum length: `1`
- Maximum length: `64`

### expected_parent_id

- Minimum length: `1`
- Maximum length: `64`

### expected_updated_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "parent_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Parent Id",
          "type": "string"
        },
        "expected_parent_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Expected Parent Id",
          "type": "string"
        },
        "expected_updated_at": {
          "format": "date-time",
          "title": "Expected Updated At",
          "type": "string"
        }
      },
      "required": [
        "parent_id",
        "expected_parent_id",
        "expected_updated_at"
      ],
      "title": "CatalogMove",
      "type": "object"
    }
    ```
