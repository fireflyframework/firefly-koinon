<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentExtraction

[All wire models](index.md)

Model aliases: `DocumentExtraction`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `document_id` | `string` | Yes | Not specified |
| `catalog_source_id` | `string` | Yes | Not specified |
| `native_source_id` | `string` | Yes | Not specified |
| `source_version_id` | `string` | Yes | Not specified |
| `extraction_id` | `string` | Yes | Not specified |
| `purpose` | `string` | Yes | Not specified |
| `coverage` | `string` | Yes | Not specified |
| `normalized_sha256` | `string` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `predecessor_extraction_id` | `string` or `null` | No | `null` |

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

### source_version_id

- Minimum length: `1`
- Maximum length: `64`

### extraction_id

- Minimum length: `1`
- Maximum length: `64`

### purpose

- Minimum length: `1`
- Maximum length: `32`

### coverage

- Minimum length: `1`
- Maximum length: `32`

### normalized_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### created_at

- Format: `"date-time"`

### predecessor_extraction_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`


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
        },
        "source_version_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Source Version Id",
          "type": "string"
        },
        "extraction_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Extraction Id",
          "type": "string"
        },
        "purpose": {
          "maxLength": 32,
          "minLength": 1,
          "title": "Purpose",
          "type": "string"
        },
        "coverage": {
          "maxLength": 32,
          "minLength": 1,
          "title": "Coverage",
          "type": "string"
        },
        "normalized_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Normalized Sha256",
          "type": "string"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "predecessor_extraction_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Predecessor Extraction Id"
        }
      },
      "required": [
        "document_id",
        "catalog_source_id",
        "native_source_id",
        "source_version_id",
        "extraction_id",
        "purpose",
        "coverage",
        "normalized_sha256",
        "created_at"
      ],
      "title": "DocumentExtraction",
      "type": "object"
    }
    ```
