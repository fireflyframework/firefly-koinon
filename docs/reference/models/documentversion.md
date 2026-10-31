<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentVersion

[All wire models](index.md)

Model aliases: `DocumentVersion`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `document_id` | `string` | Yes | Not specified |
| `catalog_source_id` | `string` | Yes | Not specified |
| `native_source_id` | `string` | Yes | Not specified |
| `source_version_id` | `string` | Yes | Not specified |
| `filename` | `string` or `null` | No | `null` |
| `media_type` | `string` or `null` | No | `null` |
| `sha256` | `string` | Yes | Not specified |
| `byte_size` | `integer` | Yes | Not specified |
| `actor` | `string` or `null` | No | `null` |
| `created_at` | `string` | Yes | Not specified |
| `predecessor_source_version_id` | `string` or `null` | No | `null` |

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

### filename

- anyOf branch 1 (`string`): Maximum length: `512`

### media_type

- anyOf branch 1 (`string`): Maximum length: `128`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`

### byte_size

- Minimum: `0`

### actor

- anyOf branch 1 (`string`): Maximum length: `512`

### created_at

- Format: `"date-time"`

### predecessor_source_version_id

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
        "filename": {
          "anyOf": [
            {
              "maxLength": 512,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Filename"
        },
        "media_type": {
          "anyOf": [
            {
              "maxLength": 128,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Media Type"
        },
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
          "type": "string"
        },
        "byte_size": {
          "minimum": 0,
          "title": "Byte Size",
          "type": "integer"
        },
        "actor": {
          "anyOf": [
            {
              "maxLength": 512,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Actor"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "predecessor_source_version_id": {
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
          "title": "Predecessor Source Version Id"
        }
      },
      "required": [
        "document_id",
        "catalog_source_id",
        "native_source_id",
        "source_version_id",
        "sha256",
        "byte_size",
        "created_at"
      ],
      "title": "DocumentVersion",
      "type": "object"
    }
    ```
