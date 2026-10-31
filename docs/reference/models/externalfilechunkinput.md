<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalFileChunkInput

[All wire models](index.md)

Model aliases: `ExternalFileChunkInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `index` | `integer` | Yes | Not specified |
| `data_base64` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### index

- Minimum: `0`
- Maximum: `511`

### data_base64

- Minimum length: `4`
- Maximum length: `87384`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "index": {
          "maximum": 511,
          "minimum": 0,
          "title": "Index",
          "type": "integer"
        },
        "data_base64": {
          "maxLength": 87384,
          "minLength": 4,
          "title": "Data Base64",
          "type": "string"
        },
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
          "type": "string"
        }
      },
      "required": [
        "index",
        "data_base64",
        "sha256"
      ],
      "title": "ExternalFileChunkInput",
      "type": "object"
    }
    ```
