<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ThreadPatch

[All wire models](index.md)

Model aliases: `ThreadPatch`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `title` | `string` or `null` | No | `null` |
| `folder_id` | `string` or `null` | No | `null` |
| `archived` | `boolean` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        },
        "title": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Title"
        },
        "folder_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Folder Id"
        },
        "archived": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Archived"
        }
      },
      "required": [
        "expected_revision"
      ],
      "title": "ThreadPatch",
      "type": "object"
    }
    ```
