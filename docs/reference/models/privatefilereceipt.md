<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# PrivateFileReceipt

[All wire models](index.md)

Model aliases: `PrivateFileReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `filename` | `string` | Yes | Not specified |
| `media_type` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `used_revision` | `integer` | Yes | Not specified |
| `availability` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### filename

- Minimum length: `1`
- Maximum length: `512`

### media_type

- Minimum length: `1`
- Maximum length: `255`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`

### used_revision

- Minimum: `1`

### availability

- Allowed values: `"available"`, `"expired"`, `"deleted"`, `"changed"`, `"unavailable"`


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
        "filename": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Filename",
          "type": "string"
        },
        "media_type": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Media Type",
          "type": "string"
        },
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
          "type": "string"
        },
        "used_revision": {
          "minimum": 1,
          "title": "Used Revision",
          "type": "integer"
        },
        "availability": {
          "enum": [
            "available",
            "expired",
            "deleted",
            "changed",
            "unavailable"
          ],
          "title": "Availability",
          "type": "string"
        }
      },
      "required": [
        "id",
        "filename",
        "media_type",
        "sha256",
        "used_revision",
        "availability"
      ],
      "title": "PrivateFileReceipt",
      "type": "object"
    }
    ```
