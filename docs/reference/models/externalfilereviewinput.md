<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalFileReviewInput

[All wire models](index.md)

Model aliases: `ExternalFileReviewInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `filename` | `string` | Yes | Not specified |
| `content_type` | `string` or `null` | No | `null` |
| `mode` | `string` | Yes | Not specified |
| `destination_id` | `string` | Yes | Not specified |
| `size_bytes` | `integer` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### filename

- Minimum length: `1`
- Maximum length: `255`

### content_type

- anyOf branch 1 (`string`): Maximum length: `128`

### mode

- Allowed values: `"document"`, `"dataset"`

### destination_id

- Minimum length: `1`
- Maximum length: `64`

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
        "filename": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Filename",
          "type": "string"
        },
        "content_type": {
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
          "title": "Content Type"
        },
        "mode": {
          "enum": [
            "document",
            "dataset"
          ],
          "title": "Mode",
          "type": "string"
        },
        "destination_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Destination Id",
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
        "filename",
        "mode",
        "destination_id",
        "size_bytes",
        "sha256"
      ],
      "title": "ExternalFileReviewInput",
      "type": "object"
    }
    ```
