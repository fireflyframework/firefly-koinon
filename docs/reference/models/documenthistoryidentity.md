<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentHistoryIdentity

[All wire models](index.md)

Model aliases: `DocumentHistoryIdentity`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `document_id` | `string` | Yes | Not specified |
| `catalog_source_id` | `string` | Yes | Not specified |
| `native_source_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### document_id

- Minimum length: `1`
- Maximum length: `64`

### catalog_source_id

- Minimum length: `1`
- Maximum length: `64`

### native_source_id

- Minimum length: `1`
- Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "document_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Document Id",
          "type": "string"
        },
        "catalog_source_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Catalog Source Id",
          "type": "string"
        },
        "native_source_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Native Source Id",
          "type": "string"
        }
      },
      "required": [
        "document_id",
        "catalog_source_id",
        "native_source_id"
      ],
      "title": "DocumentHistoryIdentity",
      "type": "object"
    }
    ```
