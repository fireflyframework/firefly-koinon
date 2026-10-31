<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SchemaTable

[All wire models](index.md)

Model aliases: `SchemaTable`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `sheet_or_json_path` | `string` or `null` | No | `null` |
| `id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `snapshot_id` | `string` or `null` | No | `null` |
| `columns` | Array of [`Column`](column.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "sheet_or_json_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sheet Or Json Path"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "snapshot_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Snapshot Id"
        },
        "columns": {
          "items": {
            "$ref": "#/$defs/Column"
          },
          "title": "Columns",
          "type": "array"
        }
      },
      "required": [
        "id",
        "name",
        "columns"
      ],
      "title": "SchemaTable",
      "type": "object"
    }
    ```
