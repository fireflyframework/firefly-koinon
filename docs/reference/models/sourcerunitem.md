<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceRunItem

[All wire models](index.md)

Model aliases: `SourceRunItem`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `object_id` | `string` | Yes | Not specified |
| `generation` | `integer` | Yes | Not specified |
| `remote_version` | `string` or `null` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `relative_path` | Array of `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `error_code` | `string` or `null` | Yes | Not specified |
| `source_id` | `string` or `null` | Yes | Not specified |
| `asset_id` | `string` or `null` | Yes | Not specified |
| `attempt_id` | `string` or `null` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### object_id

- Minimum length: `1`
- Maximum length: `64`

### generation

- Minimum: `1`

### kind

- Allowed values: `"file"`, `"folder"`, `"deleted"`, `"unknown"`

### status

- Allowed values: `"observed"`, `"downloading"`, `"processing"`, `"synchronized"`, `"searchable"`, `"skipped"`, `"conflict"`, `"retired"`, `"failed"`, `"indeterminate"`

### source_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### asset_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### attempt_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### updated_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "object_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Object Id",
          "type": "string"
        },
        "generation": {
          "minimum": 1,
          "title": "Generation",
          "type": "integer"
        },
        "remote_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Remote Version"
        },
        "kind": {
          "enum": [
            "file",
            "folder",
            "deleted",
            "unknown"
          ],
          "title": "Kind",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "relative_path": {
          "items": {
            "type": "string"
          },
          "title": "Relative Path",
          "type": "array"
        },
        "status": {
          "enum": [
            "observed",
            "downloading",
            "processing",
            "synchronized",
            "searchable",
            "skipped",
            "conflict",
            "retired",
            "failed",
            "indeterminate"
          ],
          "title": "Status",
          "type": "string"
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
          "title": "Error Code"
        },
        "source_id": {
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
          "title": "Source Id"
        },
        "asset_id": {
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
          "title": "Asset Id"
        },
        "attempt_id": {
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
          "title": "Attempt Id"
        },
        "updated_at": {
          "format": "date-time",
          "title": "Updated At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "object_id",
        "generation",
        "remote_version",
        "kind",
        "name",
        "relative_path",
        "status",
        "error_code",
        "source_id",
        "asset_id",
        "attempt_id",
        "updated_at"
      ],
      "title": "SourceRunItem",
      "type": "object"
    }
    ```
