<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourcePreviewItem

[All wire models](index.md)

Model aliases: `SourcePreviewItem`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `item_id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `version` | `string` or `null` | Yes | Not specified |
| `filename` | `string` | Yes | Not specified |
| `export_mime` | `string` or `null` | Yes | Not specified |
| `reason` | `string` or `null` | Yes | Not specified |
| `ancestry` | Array of `string` | Yes | Not specified |
| `relative_path` | Array of `string` | Yes | Not specified |
| `destination_relative_path` | Array of `string` | Yes | Not specified |
| `collision` | `string` | Yes | Not specified |
| `size_bytes` | `integer` or `null` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### collision

- Allowed values: `"none"`, `"source_name"`, `"destination_name"`, `"local_edit"`

### action

- Allowed values: `"create"`, `"replace"`, `"move"`, `"skip"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "item_id": {
          "title": "Item Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "kind": {
          "title": "Kind",
          "type": "string"
        },
        "version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Version"
        },
        "filename": {
          "title": "Filename",
          "type": "string"
        },
        "export_mime": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Export Mime"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Reason"
        },
        "ancestry": {
          "items": {
            "type": "string"
          },
          "title": "Ancestry",
          "type": "array"
        },
        "relative_path": {
          "items": {
            "type": "string"
          },
          "title": "Relative Path",
          "type": "array"
        },
        "destination_relative_path": {
          "items": {
            "type": "string"
          },
          "title": "Destination Relative Path",
          "type": "array"
        },
        "collision": {
          "enum": [
            "none",
            "source_name",
            "destination_name",
            "local_edit"
          ],
          "title": "Collision",
          "type": "string"
        },
        "size_bytes": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Size Bytes"
        },
        "action": {
          "enum": [
            "create",
            "replace",
            "move",
            "skip"
          ],
          "title": "Action",
          "type": "string"
        }
      },
      "required": [
        "item_id",
        "name",
        "kind",
        "version",
        "filename",
        "export_mime",
        "reason",
        "ancestry",
        "relative_path",
        "destination_relative_path",
        "collision",
        "size_bytes",
        "action"
      ],
      "title": "SourcePreviewItem",
      "type": "object"
    }
    ```
