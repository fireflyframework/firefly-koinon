<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# TableCoordinateManifest

[All wire models](index.md)

Model aliases: `TableCoordinateManifest`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `dataset_id` | `string` | Yes | Not specified |
| `table_id` | `string` | Yes | Not specified |
| `native_dataset_id` | `string` | Yes | Not specified |
| `native_table_id` | `string` | Yes | Not specified |
| `snapshot_id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `index_base` | `integer` | No | `0` |
| `row_count` | `integer` or `null` | No | `null` |
| `column_count` | `integer` or `null` | No | `null` |
| `artifact_id` | `string` or `null` | No | `null` |
| `run_id` | `string` or `null` | No | `null` |
| `input_sha256` | `string` or `null` | No | `null` |
| `mapping_sha256` | `string` or `null` | No | `null` |
| `source_format` | `string` or `null` | No | `null` |
| `source_variant` | `string` or `null` | No | `null` |
| `row_kind` | `string` or `null` | No | `null` |
| `source_sheet` | `string` or `null` | No | `null` |
| `source_path` | Array of `string` or `integer` | No | `[]` |
| `parser_decisions` | Array of [`CoordinateParserDecision`](coordinateparserdecision.md) | No | `[]` |
| `dependencies` | Array of [`CoordinateDependency`](coordinatedependency.md) | No | `[]` |
| `reason_code` | `string` or `null` | No | `null` |
| `rejected_source_rows` | Array of `integer` | No | `[]` |

## Model constraints

- Additional properties: permitted

## Field constraints

### dataset_id

- Minimum length: `1`
- Maximum length: `64`

### table_id

- Minimum length: `1`
- Maximum length: `64`

### native_dataset_id

- Minimum length: `1`
- Maximum length: `64`

### native_table_id

- Minimum length: `1`
- Maximum length: `64`

### snapshot_id

- Minimum length: `1`
- Maximum length: `64`

### status

- Allowed values: `"complete"`, `"partial"`, `"not_recorded"`

### index_base

- Minimum: `0`
- Maximum: `0`

### row_count

- anyOf branch 1 (`integer`): Minimum: `0`
- anyOf branch 1 (`integer`): Maximum: `9007199254740991`

### column_count

- anyOf branch 1 (`integer`): Minimum: `0`
- anyOf branch 1 (`integer`): Maximum: `9007199254740991`

### artifact_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### run_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### input_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### mapping_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### source_format

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `512`

### source_variant

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `512`

### row_kind

- anyOf branch 1 (`string`): Allowed values: `"record"`, `"sheet_row"`, `"json_array"`, `"jsonl_record"`, `"single_object"`

### source_sheet

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `512`

### source_path

- Maximum items: `64`
- Each item: anyOf branch 1 (`string`): Maximum length: `4096`
- Each item: anyOf branch 2 (`integer`): Minimum: `0`
- Each item: anyOf branch 2 (`integer`): Maximum: `9007199254740991`

### parser_decisions

- Maximum items: `128`

### dependencies

- Maximum items: `128`

### reason_code

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `512`

### rejected_source_rows

- Maximum items: `1024`
- Each item: Minimum: `0`
- Each item: Maximum: `9007199254740991`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
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
        "native_dataset_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Native Dataset Id",
          "type": "string"
        },
        "native_table_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Native Table Id",
          "type": "string"
        },
        "snapshot_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Snapshot Id",
          "type": "string"
        },
        "status": {
          "enum": [
            "complete",
            "partial",
            "not_recorded"
          ],
          "title": "Status",
          "type": "string"
        },
        "index_base": {
          "default": 0,
          "maximum": 0,
          "minimum": 0,
          "title": "Index Base",
          "type": "integer"
        },
        "row_count": {
          "anyOf": [
            {
              "maximum": 9007199254740991,
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Row Count"
        },
        "column_count": {
          "anyOf": [
            {
              "maximum": 9007199254740991,
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Column Count"
        },
        "artifact_id": {
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
          "title": "Artifact Id"
        },
        "run_id": {
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
          "title": "Run Id"
        },
        "input_sha256": {
          "anyOf": [
            {
              "pattern": "^[a-f0-9]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Input Sha256"
        },
        "mapping_sha256": {
          "anyOf": [
            {
              "pattern": "^[a-f0-9]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Mapping Sha256"
        },
        "source_format": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Format"
        },
        "source_variant": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Variant"
        },
        "row_kind": {
          "anyOf": [
            {
              "enum": [
                "record",
                "sheet_row",
                "json_array",
                "jsonl_record",
                "single_object"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Row Kind"
        },
        "source_sheet": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Sheet"
        },
        "source_path": {
          "default": [],
          "items": {
            "anyOf": [
              {
                "maxLength": 4096,
                "type": "string"
              },
              {
                "maximum": 9007199254740991,
                "minimum": 0,
                "type": "integer"
              }
            ]
          },
          "maxItems": 64,
          "title": "Source Path",
          "type": "array"
        },
        "parser_decisions": {
          "default": [],
          "items": {
            "$ref": "#/$defs/CoordinateParserDecision"
          },
          "maxItems": 128,
          "title": "Parser Decisions",
          "type": "array"
        },
        "dependencies": {
          "default": [],
          "items": {
            "$ref": "#/$defs/CoordinateDependency"
          },
          "maxItems": 128,
          "title": "Dependencies",
          "type": "array"
        },
        "reason_code": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason Code"
        },
        "rejected_source_rows": {
          "default": [],
          "items": {
            "maximum": 9007199254740991,
            "minimum": 0,
            "type": "integer"
          },
          "maxItems": 1024,
          "title": "Rejected Source Rows",
          "type": "array"
        }
      },
      "required": [
        "dataset_id",
        "table_id",
        "native_dataset_id",
        "native_table_id",
        "snapshot_id",
        "status"
      ],
      "title": "TableCoordinateManifest",
      "type": "object"
    }
    ```
