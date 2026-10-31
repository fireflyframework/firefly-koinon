<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProvenanceArtifact

[All wire models](index.md)

Model aliases: `ProvenanceArtifact`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `original_filename` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `byte_size` | `integer` | Yes | Not specified |
| `file_format` | `string` | Yes | Not specified |
| `compression` | `string` | Yes | Not specified |
| `actor` | `string` | Yes | Not specified |
| `admitted_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### original_filename

- Minimum length: `1`
- Maximum length: `255`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`

### byte_size

- Minimum: `0`

### file_format

- Minimum length: `1`
- Maximum length: `64`

### compression

- Maximum length: `64`

### actor

- Minimum length: `1`
- Maximum length: `512`

### admitted_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "original_filename": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Original Filename",
          "type": "string"
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
        "file_format": {
          "maxLength": 64,
          "minLength": 1,
          "title": "File Format",
          "type": "string"
        },
        "compression": {
          "maxLength": 64,
          "title": "Compression",
          "type": "string"
        },
        "actor": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Actor",
          "type": "string"
        },
        "admitted_at": {
          "format": "date-time",
          "title": "Admitted At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "original_filename",
        "sha256",
        "byte_size",
        "file_format",
        "compression",
        "actor",
        "admitted_at"
      ],
      "title": "ProvenanceArtifact",
      "type": "object"
    }
    ```
