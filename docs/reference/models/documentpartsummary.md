<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentPartSummary

[All wire models](index.md)

Model aliases: `DocumentPartSummary`.

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
| `ordinal` | `integer` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `recorded_page` | `integer` or `null` | No | `null` |
| `page_basis` | `string` or `null` | No | `null` |
| `char_start` | `integer` or `null` | No | `null` |
| `char_end` | `integer` or `null` | No | `null` |
| `offset_basis` | `string` or `null` | No | `null` |
| `created_at` | `string` | Yes | Not specified |

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

- Allowed values: `"artifact"`, `"section"`, `"chunk"`, `"page"`

### ordinal

- Minimum: `0`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`

### recorded_page

- anyOf branch 1 (`integer`): Minimum: `1`

### page_basis

- anyOf branch 1 (`string`): Exact value: `"recorded_loader"`

### char_start

- anyOf branch 1 (`integer`): Minimum: `0`

### char_end

- anyOf branch 1 (`integer`): Minimum: `0`

### offset_basis

- anyOf branch 1 (`string`): Maximum length: `64`

### created_at

- Format: `"date-time"`


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
            "artifact",
            "section",
            "chunk",
            "page"
          ],
          "title": "Kind",
          "type": "string"
        },
        "ordinal": {
          "minimum": 0,
          "title": "Ordinal",
          "type": "integer"
        },
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
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
          "anyOf": [
            {
              "const": "recorded_loader",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page Basis"
        },
        "char_start": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Char Start"
        },
        "char_end": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Char End"
        },
        "offset_basis": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Offset Basis"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
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
        "ordinal",
        "sha256",
        "created_at"
      ],
      "title": "DocumentPartSummary",
      "type": "object"
    }
    ```
