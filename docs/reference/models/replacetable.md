<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ReplaceTable

[All wire models](index.md)

Model aliases: `ReplaceTable`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |
| `dataset_id` | `string` | Yes | Not specified |
| `table_id` | `string` | Yes | Not specified |
| `expected_snapshot_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`

### action

- Exact value: `"replace_table"`

### dataset_id

- Minimum length: `1`
- Maximum length: `64`

### table_id

- Minimum length: `1`
- Maximum length: `64`

### expected_snapshot_id

- Minimum length: `1`
- Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        },
        "action": {
          "const": "replace_table",
          "title": "Action",
          "type": "string"
        },
        "dataset_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Dataset Id",
          "type": "string"
        },
        "table_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Table Id",
          "type": "string"
        },
        "expected_snapshot_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Expected Snapshot Id",
          "type": "string"
        }
      },
      "required": [
        "expected_revision",
        "action",
        "dataset_id",
        "table_id",
        "expected_snapshot_id"
      ],
      "title": "ReplaceTable",
      "type": "object"
    }
    ```
