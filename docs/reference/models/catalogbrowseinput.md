<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CatalogBrowseInput

[All wire models](index.md)

Model aliases: `CatalogBrowseInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `parent_id` | `string` or `null` | No | `null` |
| `workspace_id` | `string` or `null` | No | `null` |
| `project_id` | `string` or `null` | No | `null` |
| `kind` | `string` or `null` | No | `null` |
| `include_archived` | `boolean` | No | `false` |
| `view` | `string` | No | `"library"` |
| `q` | `string` | No | `""` |
| `status` | `string` or `null` | No | `null` |
| `format` | `string` or `null` | No | `null` |
| `tag` | `string` or `null` | No | `null` |
| `page_size` | `integer` | No | `50` |
| `sort` | `string` | No | `"name"` |
| `order` | `string` | No | `"asc"` |
| `cursor` | `string` or `null` | No | `null` |
| `reader_source_connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### parent_id

- anyOf branch 1 (`string`): Maximum length: `64`

### workspace_id

- anyOf branch 1 (`string`): Maximum length: `64`

### project_id

- anyOf branch 1 (`string`): Maximum length: `64`

### kind

- anyOf branch 1 (`string`): Maximum length: `32`

### view

- Allowed values: `"raw"`, `"library"`

### q

- Maximum length: `255`

### status

- anyOf branch 1 (`string`): Maximum length: `32`

### format

- anyOf branch 1 (`string`): Maximum length: `32`

### tag

- anyOf branch 1 (`string`): Maximum length: `64`

### page_size

- Minimum: `1`
- Maximum: `100`

### sort

- Allowed values: `"name"`, `"kind"`, `"created_at"`, `"updated_at"`

### order

- Allowed values: `"asc"`, `"desc"`

### cursor

- anyOf branch 1 (`string`): Minimum length: `43`
- anyOf branch 1 (`string`): Maximum length: `43`

### reader_source_connections

- anyOf branch 1 (Array of [`ReaderSourceSelection`](readersourceselection.md)): Maximum items: `100`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "parent_id": {
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
          "title": "Parent Id"
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
        "kind": {
          "anyOf": [
            {
              "maxLength": 32,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Kind"
        },
        "include_archived": {
          "default": false,
          "title": "Include Archived",
          "type": "boolean"
        },
        "view": {
          "default": "library",
          "enum": [
            "raw",
            "library"
          ],
          "title": "View",
          "type": "string"
        },
        "q": {
          "default": "",
          "maxLength": 255,
          "title": "Q",
          "type": "string"
        },
        "status": {
          "anyOf": [
            {
              "maxLength": 32,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Status"
        },
        "format": {
          "anyOf": [
            {
              "maxLength": 32,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Format"
        },
        "tag": {
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
          "title": "Tag"
        },
        "page_size": {
          "default": 50,
          "maximum": 100,
          "minimum": 1,
          "title": "Page Size",
          "type": "integer"
        },
        "sort": {
          "default": "name",
          "enum": [
            "name",
            "kind",
            "created_at",
            "updated_at"
          ],
          "title": "Sort",
          "type": "string"
        },
        "order": {
          "default": "asc",
          "enum": [
            "asc",
            "desc"
          ],
          "title": "Order",
          "type": "string"
        },
        "cursor": {
          "anyOf": [
            {
              "maxLength": 43,
              "minLength": 43,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Cursor"
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
      "title": "CatalogBrowseInput",
      "type": "object"
    }
    ```
