<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SqlAttemptReceipt

[All wire models](index.md)

Model aliases: `SqlAttemptReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `result_id` | `string` | Yes | Not specified |
| `generation_id` | `string` or `null` | No | `null` |
| `ordinal` | `integer` | Yes | Not specified |
| `stage` | `string` | Yes | Not specified |
| `statement_sha256` | `string` | Yes | Not specified |
| `statement` | `string` or `null` | No | `null` |
| `classification` | `string` or `null` | No | `null` |
| `outcome` | `string` | Yes | Not specified |
| `executed` | `boolean` | Yes | Not specified |
| `snapshot_pins` | Map of string keys to `string` | No | Not specified |
| `row_count` | `integer` or `null` | No | `null` |
| `truncated` | `boolean` or `null` | No | `null` |
| `reason_code` | `string` or `null` | No | `null` |
| `engine` | `string` or `null` | No | `null` |
| `database` | `string` or `null` | No | `null` |
| `catalog` | `string` or `null` | No | `null` |
| `schema` | `string` or `null` | No | `null` |
| `execution_kind` | `string` or `null` | No | `null` |
| `dataset_id` | `string` or `null` | No | `null` |
| `native_dataset_id` | `string` or `null` | No | `null` |
| `tables` | Array of [`NativeTableSnapshot`](nativetablesnapshot.md) | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### result_id

- Minimum length: `1`
- Maximum length: `64`

### ordinal

- Minimum: `1`
- Maximum: `1000`

### stage

- Minimum length: `1`
- Maximum length: `64`

### statement_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### statement

- anyOf branch 1 (`string`): Maximum length: `32768`

### classification

- anyOf branch 1 (`string`): Maximum length: `64`

### outcome

- Minimum length: `1`
- Maximum length: `64`

### snapshot_pins

- Maximum properties: `500`
- Additional properties: `string`

### row_count

- anyOf branch 1 (`integer`): Minimum: `0`

### reason_code

- anyOf branch 1 (`string`): Maximum length: `64`

### engine

- anyOf branch 1 (`string`): Maximum length: `64`

### database

- anyOf branch 1 (`string`): Maximum length: `255`

### catalog

- anyOf branch 1 (`string`): Maximum length: `255`

### schema

- anyOf branch 1 (`string`): Maximum length: `255`

### execution_kind

- anyOf branch 1 (`string`): Allowed values: `"imported_snapshot"`, `"computed"`

### dataset_id

- anyOf branch 1 (`string`): Maximum length: `64`

### native_dataset_id

- anyOf branch 1 (`string`): Maximum length: `64`

### tables

- Maximum items: `500`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "result_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Result Id",
          "type": "string"
        },
        "generation_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Generation Id"
        },
        "ordinal": {
          "maximum": 1000,
          "minimum": 1,
          "title": "Ordinal",
          "type": "integer"
        },
        "stage": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Stage",
          "type": "string"
        },
        "statement_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Statement Sha256",
          "type": "string"
        },
        "statement": {
          "anyOf": [
            {
              "maxLength": 32768,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Statement"
        },
        "classification": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Classification"
        },
        "outcome": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Outcome",
          "type": "string"
        },
        "executed": {
          "title": "Executed",
          "type": "boolean"
        },
        "snapshot_pins": {
          "additionalProperties": {
            "type": "string"
          },
          "maxProperties": 500,
          "title": "Snapshot Pins",
          "type": "object"
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
        "truncated": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Truncated"
        },
        "reason_code": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason Code"
        },
        "engine": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Engine"
        },
        "database": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Database"
        },
        "catalog": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Catalog"
        },
        "schema": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Schema"
        },
        "execution_kind": {
          "anyOf": [
            {
              "enum": [
                "imported_snapshot",
                "computed"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Execution Kind"
        },
        "dataset_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Dataset Id"
        },
        "native_dataset_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Native Dataset Id"
        },
        "tables": {
          "items": {
            "$ref": "#/$defs/NativeTableSnapshot"
          },
          "maxItems": 500,
          "title": "Tables",
          "type": "array"
        }
      },
      "required": [
        "result_id",
        "ordinal",
        "stage",
        "statement_sha256",
        "outcome",
        "executed"
      ],
      "title": "SqlAttemptReceipt",
      "type": "object"
    }
    ```
