<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DatasetFileAppendResult

[All wire models](index.md)

Model aliases: `DatasetFileAppendResult`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `dataset_id` | `string` | Yes | Not specified |
| `file_version_id` | `string` | Yes | Not specified |
| `filename` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `byte_size` | `integer` | Yes | Not specified |
| `table_ids` | Array of `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### sha256

- Pattern: `"^[0-9a-f]{64}$"`

### byte_size

- Minimum: `1`

### table_ids

- Minimum items: `1`
- Maximum items: `128`

### status

- Exact value: `"ready"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "dataset_id": {
          "title": "Dataset Id",
          "type": "string"
        },
        "file_version_id": {
          "title": "File Version Id",
          "type": "string"
        },
        "filename": {
          "title": "Filename",
          "type": "string"
        },
        "sha256": {
          "pattern": "^[0-9a-f]{64}$",
          "title": "Sha256",
          "type": "string"
        },
        "byte_size": {
          "minimum": 1,
          "title": "Byte Size",
          "type": "integer"
        },
        "table_ids": {
          "items": {
            "type": "string"
          },
          "maxItems": 128,
          "minItems": 1,
          "title": "Table Ids",
          "type": "array"
        },
        "status": {
          "const": "ready",
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "dataset_id",
        "file_version_id",
        "filename",
        "sha256",
        "byte_size",
        "table_ids",
        "status"
      ],
      "title": "DatasetFileAppendResult",
      "type": "object"
    }
    ```
