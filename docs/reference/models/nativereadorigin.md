<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NativeReadOrigin

[All wire models](index.md)

Model aliases: `NativeReadOrigin`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `original_filename` | `string` or `null` | No | `null` |
| `sheet_or_json_path` | `string` or `null` | No | `null` |
| `connection_id` | `string` or `null` | No | `null` |
| `connection_name` | `string` or `null` | No | `null` |
| `database` | `string` or `null` | No | `null` |
| `schema` | `string` or `null` | No | `null` |
| `table` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### original_filename

- anyOf branch 1 (`string`): Maximum length: `512`

### sheet_or_json_path

- anyOf branch 1 (`string`): Maximum length: `1024`

### connection_id

- anyOf branch 1 (`string`): Maximum length: `255`

### connection_name

- anyOf branch 1 (`string`): Maximum length: `255`

### database

- anyOf branch 1 (`string`): Maximum length: `255`

### schema

- anyOf branch 1 (`string`): Maximum length: `255`

### table

- anyOf branch 1 (`string`): Maximum length: `512`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "original_filename": {
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
          "title": "Original Filename"
        },
        "sheet_or_json_path": {
          "anyOf": [
            {
              "maxLength": 1024,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sheet Or Json Path"
        },
        "connection_id": {
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
          "title": "Connection Id"
        },
        "connection_name": {
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
          "title": "Connection Name"
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
        "table": {
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
          "title": "Table"
        }
      },
      "title": "NativeReadOrigin",
      "type": "object"
    }
    ```
