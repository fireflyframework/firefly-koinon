<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# FileManifestItem

[All wire models](index.md)

Model aliases: `FileManifestItem`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `client_item_id` | `string` | Yes | Not specified |
| `filename` | `string` | Yes | Not specified |
| `mode` | `string` | Yes | Not specified |
| `size_bytes` | `integer` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### client_item_id

- Minimum length: `1`
- Maximum length: `64`

### filename

- Minimum length: `1`
- Maximum length: `255`

### mode

- Allowed values: `"document"`, `"dataset"`

### size_bytes

- Minimum: `1`
- Maximum: `134217728`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "client_item_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Client Item Id",
          "type": "string"
        },
        "filename": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Filename",
          "type": "string"
        },
        "mode": {
          "enum": [
            "document",
            "dataset"
          ],
          "title": "Mode",
          "type": "string"
        },
        "size_bytes": {
          "maximum": 134217728,
          "minimum": 1,
          "title": "Size Bytes",
          "type": "integer"
        },
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
          "type": "string"
        }
      },
      "required": [
        "client_item_id",
        "filename",
        "mode",
        "size_bytes",
        "sha256"
      ],
      "title": "FileManifestItem",
      "type": "object"
    }
    ```
