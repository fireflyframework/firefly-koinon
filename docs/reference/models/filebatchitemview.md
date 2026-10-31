<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# FileBatchItemView

[All wire models](index.md)

Model aliases: `FileBatchItemView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `client_item_id` | `string` | Yes | Not specified |
| `filename` | `string` | Yes | Not specified |
| `mode` | `string` | Yes | Not specified |
| `size_bytes` | `integer` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `source_id` | `string` | Yes | Not specified |
| `asset_id` | `string` | Yes | Not specified |
| `job_id` | `string` or `null` | Yes | Not specified |
| `file_version_id` | `string` or `null` | No | `null` |
| `table_ids` | Array of `string` | No | Not specified |
| `source_version_id` | `string` or `null` | No | `null` |
| `extraction_id` | `string` or `null` | No | `null` |
| `error_code` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### mode

- Allowed values: `"document"`, `"dataset"`

### status

- Allowed values: `"awaiting_upload"`, `"staged"`, `"queued"`, `"running"`, `"succeeded"`, `"failed"`, `"cancelled"`, `"reconciling"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "client_item_id": {
          "title": "Client Item Id",
          "type": "string"
        },
        "filename": {
          "title": "Filename",
          "type": "string"
        },
        "mode": {
          "enum": [
            "document",
            "dataset"
          ],
          "title": "Mode",
          "type": "string"
        },
        "size_bytes": {
          "title": "Size Bytes",
          "type": "integer"
        },
        "sha256": {
          "title": "Sha256",
          "type": "string"
        },
        "status": {
          "enum": [
            "awaiting_upload",
            "staged",
            "queued",
            "running",
            "succeeded",
            "failed",
            "cancelled",
            "reconciling"
          ],
          "title": "Status",
          "type": "string"
        },
        "source_id": {
          "title": "Source Id",
          "type": "string"
        },
        "asset_id": {
          "title": "Asset Id",
          "type": "string"
        },
        "job_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Job Id"
        },
        "file_version_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "File Version Id"
        },
        "table_ids": {
          "items": {
            "type": "string"
          },
          "title": "Table Ids",
          "type": "array"
        },
        "source_version_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Version Id"
        },
        "extraction_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Extraction Id"
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Code"
        }
      },
      "required": [
        "id",
        "client_item_id",
        "filename",
        "mode",
        "size_bytes",
        "sha256",
        "status",
        "source_id",
        "asset_id",
        "job_id"
      ],
      "title": "FileBatchItemView",
      "type": "object"
    }
    ```
