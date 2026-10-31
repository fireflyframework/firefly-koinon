<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentPartContent

[All wire models](index.md)

Model aliases: `DocumentPartContent`.

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
| `source_part_id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `text` | `string` | Yes | Not specified |
| `recorded_page` | `integer` or `null` | No | `null` |
| `page_basis` | `string` | Yes | Not specified |
| `raw_sha256` | `string` | Yes | Not specified |
| `normalized_sha256` | `string` | Yes | Not specified |
| `input_sha256` | `string` | Yes | Not specified |

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

### source_part_id

- Minimum length: `1`
- Maximum length: `64`

### kind

- Allowed values: `"chunk"`, `"page"`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`

### text

- Maximum length: `1000000`

### recorded_page

- anyOf branch 1 (`integer`): Minimum: `1`

### page_basis

- Exact value: `"recorded_loader"`

### raw_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### normalized_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### input_sha256

- Pattern: `"^[a-f0-9]{64}$"`


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
        "source_part_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Source Part Id",
          "type": "string"
        },
        "kind": {
          "enum": [
            "chunk",
            "page"
          ],
          "title": "Kind",
          "type": "string"
        },
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
          "type": "string"
        },
        "text": {
          "maxLength": 1000000,
          "title": "Text",
          "type": "string"
        },
        "recorded_page": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Recorded Page"
        },
        "page_basis": {
          "const": "recorded_loader",
          "title": "Page Basis",
          "type": "string"
        },
        "raw_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Raw Sha256",
          "type": "string"
        },
        "normalized_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Normalized Sha256",
          "type": "string"
        },
        "input_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Input Sha256",
          "type": "string"
        }
      },
      "required": [
        "document_id",
        "catalog_source_id",
        "native_source_id",
        "source_version_id",
        "extraction_id",
        "source_part_id",
        "kind",
        "sha256",
        "text",
        "page_basis",
        "raw_sha256",
        "normalized_sha256",
        "input_sha256"
      ],
      "title": "DocumentPartContent",
      "type": "object"
    }
    ```
