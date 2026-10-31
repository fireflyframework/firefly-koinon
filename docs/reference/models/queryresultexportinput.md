<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryResultExportInput

[All wire models](index.md)

Model aliases: `QueryResultExportInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `dataset_id` | `string` | Yes | Not specified |
| `query_id` | `string` | Yes | Not specified |
| `format` | `string` | Yes | Not specified |
| `csv_mode` | `string` | No | `"spreadsheet_safe"` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### kind

- Exact value: `"query_result"`

### dataset_id

- Minimum length: `1`
- Maximum length: `64`

### query_id

- Minimum length: `1`
- Maximum length: `64`

### format

- Allowed values: `"parquet"`, `"csv"`, `"jsonl"`

### csv_mode

- Allowed values: `"spreadsheet_safe"`, `"exact"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "query_result",
          "title": "Kind",
          "type": "string"
        },
        "dataset_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Dataset Id",
          "type": "string"
        },
        "query_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Query Id",
          "type": "string"
        },
        "format": {
          "enum": [
            "parquet",
            "csv",
            "jsonl"
          ],
          "title": "Format",
          "type": "string"
        },
        "csv_mode": {
          "default": "spreadsheet_safe",
          "enum": [
            "spreadsheet_safe",
            "exact"
          ],
          "title": "Csv Mode",
          "type": "string"
        }
      },
      "required": [
        "kind",
        "dataset_id",
        "query_id",
        "format"
      ],
      "title": "QueryResultExportInput",
      "type": "object"
    }
    ```
