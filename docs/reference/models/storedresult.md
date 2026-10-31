<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# StoredResult

[All wire models](index.md)

Model aliases: `StoredResult`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `query_id` | `string` | Yes | Not specified |
| `asset_id` | `string` | Yes | Not specified |
| `revision` | `string` | Yes | Not specified |
| `row_count` | `integer` | Yes | Not specified |
| `row_cap` | `integer` or `null` | Yes | Not specified |
| `truncated` | `boolean` or `null` | Yes | Not specified |
| `completeness` | `string` | No | `"unknown"` |
| `byte_size` | `integer` | Yes | Not specified |
| `columns` | Array of [`ResultColumn`](resultcolumn.md) | No | `[]` |
| `snapshot_ids` | Array of `string` | No | `[]` |
| `snapshot_manifest_complete` | `boolean` | No | `false` |
| `expires_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### query_id

- Minimum length: `1`
- Maximum length: `64`

### asset_id

- Minimum length: `1`
- Maximum length: `64`

### revision

- Pattern: `"^[a-f0-9]{64}$"`

### row_count

- Minimum: `0`

### row_cap

- anyOf branch 1 (`integer`): Minimum: `1`

### completeness

- Allowed values: `"bounded"`, `"unknown"`

### byte_size

- Minimum: `0`

### columns

- Maximum items: `2000`

### snapshot_ids

- Maximum items: `500`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`

### expires_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "query_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Query Id",
          "type": "string"
        },
        "asset_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Asset Id",
          "type": "string"
        },
        "revision": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Revision",
          "type": "string"
        },
        "row_count": {
          "minimum": 0,
          "title": "Row Count",
          "type": "integer"
        },
        "row_cap": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Row Cap"
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
          "title": "Truncated"
        },
        "completeness": {
          "default": "unknown",
          "enum": [
            "bounded",
            "unknown"
          ],
          "title": "Completeness",
          "type": "string"
        },
        "byte_size": {
          "minimum": 0,
          "title": "Byte Size",
          "type": "integer"
        },
        "columns": {
          "default": [],
          "items": {
            "$ref": "#/$defs/ResultColumn"
          },
          "maxItems": 2000,
          "title": "Columns",
          "type": "array"
        },
        "snapshot_ids": {
          "default": [],
          "items": {
            "maxLength": 64,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 500,
          "title": "Snapshot Ids",
          "type": "array"
        },
        "snapshot_manifest_complete": {
          "default": false,
          "title": "Snapshot Manifest Complete",
          "type": "boolean"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        }
      },
      "required": [
        "query_id",
        "asset_id",
        "revision",
        "row_count",
        "row_cap",
        "truncated",
        "byte_size",
        "expires_at"
      ],
      "title": "StoredResult",
      "type": "object"
    }
    ```
