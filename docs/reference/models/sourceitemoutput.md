<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceItemOutput

[All wire models](index.md)

Model aliases: `SourceItemOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `item_id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `version` | `string` or `null` | Yes | Not specified |
| `size_bytes` | `integer` or `null` | Yes | Not specified |
| `mime_type` | `string` | Yes | Not specified |
| `parents` | Array of `string` | Yes | Not specified |
| `can_download` | `boolean` or `null` | Yes | Not specified |
| `modified_at` | `string` or `null` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"file"`, `"folder"`, `"shortcut"`


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
          "enum": [
            "file",
            "folder",
            "shortcut"
          ],
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
        "mime_type": {
          "title": "Mime Type",
          "type": "string"
        },
        "parents": {
          "items": {
            "type": "string"
          },
          "title": "Parents",
          "type": "array"
        },
        "can_download": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "title": "Can Download"
        },
        "modified_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Modified At"
        }
      },
      "required": [
        "item_id",
        "name",
        "kind",
        "version",
        "size_bytes",
        "mime_type",
        "parents",
        "can_download",
        "modified_at"
      ],
      "title": "SourceItemOutput",
      "type": "object"
    }
    ```
