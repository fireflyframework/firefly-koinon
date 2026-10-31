<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NativeTableSnapshot

[All wire models](index.md)

Model aliases: `NativeTableSnapshot`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `table_id` | `string` | Yes | Not specified |
| `table_name` | `string` | Yes | Not specified |
| `snapshot_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### table_id

- Minimum length: `1`
- Maximum length: `64`

### table_name

- Minimum length: `1`
- Maximum length: `512`

### snapshot_id

- Minimum length: `1`
- Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "table_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Table Id",
          "type": "string"
        },
        "table_name": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Table Name",
          "type": "string"
        },
        "snapshot_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Snapshot Id",
          "type": "string"
        }
      },
      "required": [
        "table_id",
        "table_name",
        "snapshot_id"
      ],
      "title": "NativeTableSnapshot",
      "type": "object"
    }
    ```
