<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CatalogSummary

[All wire models](index.md)

Model aliases: `CatalogSummary`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `child_count` | `integer` or `null` | No | `null` |
| `document_count` | `integer` or `null` | No | `null` |
| `dataset_count` | `integer` or `null` | No | `null` |
| `table_count` | `integer` or `null` | No | `null` |
| `row_count` | `integer` or `null` | No | `null` |
| `column_count` | `integer` or `null` | No | `null` |
| `page_count` | `integer` or `null` | No | `null` |
| `size_bytes` | `integer` or `null` | No | `null` |
| `format` | `string` or `null` | No | `null` |
| `language` | `string` or `null` | No | `null` |
| `tags` | Array of `string` | No | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "child_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Child Count"
        },
        "document_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Document Count"
        },
        "dataset_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Dataset Count"
        },
        "table_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Table Count"
        },
        "row_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Row Count"
        },
        "column_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Column Count"
        },
        "page_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page Count"
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
          "default": null,
          "title": "Size Bytes"
        },
        "format": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Format"
        },
        "language": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Language"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "title": "Tags",
          "type": "array"
        }
      },
      "title": "CatalogSummary",
      "type": "object"
    }
    ```
