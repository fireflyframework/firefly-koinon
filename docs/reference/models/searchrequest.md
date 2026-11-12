<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SearchRequest

[All wire models](index.md)

Model aliases: `SearchRequest`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `reader_source_connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) or `null` | No | `null` |
| `question` | `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | No | `null` |
| `project_id` | `string` or `null` | No | `null` |
| `collection_id` | `string` or `null` | No | `null` |
| `asset_ids` | Array of `string` or `null` | No | `null` |
| `limit` | `integer` | No | `10` |
| `answer` | `boolean` | No | `false` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### reader_source_connections

- anyOf branch 1 (Array of [`ReaderSourceSelection`](readersourceselection.md)): Maximum items: `100`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
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
        },
        "question": {
          "title": "Question",
          "type": "string"
        },
        "workspace_id": {
          "anyOf": [
            {
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
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Project Id"
        },
        "collection_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Collection Id"
        },
        "asset_ids": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Asset Ids"
        },
        "limit": {
          "default": 10,
          "title": "Limit",
          "type": "integer"
        },
        "answer": {
          "default": false,
          "title": "Answer",
          "type": "boolean"
        }
      },
      "required": [
        "question"
      ],
      "title": "SearchRequest",
      "type": "object"
    }
    ```
