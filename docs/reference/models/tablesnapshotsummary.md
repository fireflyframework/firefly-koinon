<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# TableSnapshotSummary

[All wire models](index.md)

Model aliases: `TableSnapshotSummary`.

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
| `snapshot_status` | `string` | Yes | Not specified |
| `level` | `string` | Yes | Not specified |
| `operation` | `string` or `null` | No | `null` |
| `predecessor_snapshot_id` | `string` or `null` | No | `null` |
| `artifact` | [`ProvenanceArtifact`](provenanceartifact.md) or `null` | No | `null` |
| `sheet_or_json_path` | `string` or `null` | No | `null` |
| `table_label` | `string` or `null` | No | `null` |
| `parquet_sha256` | `string` or `null` | No | `null` |
| `parquet_byte_size` | `integer` or `null` | No | `null` |
| `schema_sha256` | `string` or `null` | No | `null` |
| `row_count` | `integer` or `null` | No | `null` |
| `actor` | `string` or `null` | No | `null` |
| `recorded_at` | `string` or `null` | No | `null` |

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

- Allowed values: `"recorded"`, `"not_recorded"`

### snapshot_status

- Allowed values: `"PARTIAL"`, `"READY"`, `"FAILED"`

### level

- Exact value: `"file_section"`

### operation

- anyOf branch 1 (`string`): Allowed values: `"upload"`, `"replace"`, `"reingest"`

### predecessor_snapshot_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### sheet_or_json_path

- anyOf branch 1 (`string`): Maximum length: `4096`

### table_label

- anyOf branch 1 (`string`): Maximum length: `512`

### parquet_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### parquet_byte_size

- anyOf branch 1 (`integer`): Minimum: `0`

### schema_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### row_count

- anyOf branch 1 (`integer`): Minimum: `0`

### actor

- anyOf branch 1 (`string`): Maximum length: `512`

### recorded_at

- anyOf branch 1 (`string`): Format: `"date-time"`


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
            "recorded",
            "not_recorded"
          ],
          "title": "Status",
          "type": "string"
        },
        "snapshot_status": {
          "enum": [
            "PARTIAL",
            "READY",
            "FAILED"
          ],
          "title": "Snapshot Status",
          "type": "string"
        },
        "level": {
          "const": "file_section",
          "title": "Level",
          "type": "string"
        },
        "operation": {
          "anyOf": [
            {
              "enum": [
                "upload",
                "replace",
                "reingest"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Operation"
        },
        "predecessor_snapshot_id": {
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
          "title": "Predecessor Snapshot Id"
        },
        "artifact": {
          "anyOf": [
            {
              "$ref": "#/$defs/ProvenanceArtifact"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "sheet_or_json_path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sheet Or Json Path"
        },
        "table_label": {
          "anyOf": [
            {
              "maxLength": 512,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Table Label"
        },
        "parquet_sha256": {
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
          "title": "Parquet Sha256"
        },
        "parquet_byte_size": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parquet Byte Size"
        },
        "schema_sha256": {
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
          "title": "Schema Sha256"
        },
        "row_count": {
          "anyOf": [
            {
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
        "actor": {
          "anyOf": [
            {
              "maxLength": 512,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Actor"
        },
        "recorded_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Recorded At"
        }
      },
      "required": [
        "dataset_id",
        "table_id",
        "native_dataset_id",
        "native_table_id",
        "snapshot_id",
        "status",
        "snapshot_status",
        "level"
      ],
      "title": "TableSnapshotSummary",
      "type": "object"
    }
    ```
