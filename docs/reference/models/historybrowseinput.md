<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# HistoryBrowseInput

[All wire models](index.md)

Model aliases: `HistoryBrowseInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `q` | `string` | No | `""` |
| `page_size` | `integer` | No | `25` |
| `cursor` | `string` or `null` | No | `null` |
| `status` | `string` | No | `"active"` |
| `folder_id` | `string` or `null` | No | `null` |
| `workspace_id` | `string` or `null` | No | `null` |
| `project_id` | `string` or `null` | No | `null` |
| `unfiled` | `boolean` | No | `false` |
| `reader_source_connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### q

- Maximum length: `255`

### page_size

- Minimum: `1`
- Maximum: `100`

### cursor

- anyOf branch 1 (`string`): Maximum length: `128`

### status

- Allowed values: `"active"`, `"archived"`, `"all"`

### folder_id

- anyOf branch 1 (`string`): Maximum length: `64`

### workspace_id

- anyOf branch 1 (`string`): Maximum length: `64`

### project_id

- anyOf branch 1 (`string`): Maximum length: `64`

### reader_source_connections

- anyOf branch 1 (Array of [`ReaderSourceSelection`](readersourceselection.md)): Maximum items: `100`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "q": {
          "default": "",
          "maxLength": 255,
          "title": "Q",
          "type": "string"
        },
        "page_size": {
          "default": 25,
          "maximum": 100,
          "minimum": 1,
          "title": "Page Size",
          "type": "integer"
        },
        "cursor": {
          "anyOf": [
            {
              "maxLength": 128,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Cursor"
        },
        "status": {
          "default": "active",
          "enum": [
            "active",
            "archived",
            "all"
          ],
          "title": "Status",
          "type": "string"
        },
        "folder_id": {
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
          "title": "Folder Id"
        },
        "workspace_id": {
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
          "title": "Workspace Id"
        },
        "project_id": {
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
          "title": "Project Id"
        },
        "unfiled": {
          "default": false,
          "title": "Unfiled",
          "type": "boolean"
        },
        "reader_source_connections": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/ReaderSourceSelection"
              },
              "maxItems": 100,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reader Source Connections"
        }
      },
      "title": "HistoryBrowseInput",
      "type": "object"
    }
    ```
