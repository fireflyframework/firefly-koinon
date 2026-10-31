<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryRequest

[All wire models](index.md)

Model aliases: `QueryRequest`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `dataset_id` | `string` | Yes | Not specified |
| `question` | `string` | No | `""` |
| `conversation_id` | `string` or `null` | No | `null` |
| `sql` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "dataset_id": {
          "title": "Dataset Id",
          "type": "string"
        },
        "question": {
          "default": "",
          "title": "Question",
          "type": "string"
        },
        "conversation_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Conversation Id"
        },
        "sql": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sql"
        }
      },
      "required": [
        "dataset_id"
      ],
      "title": "QueryRequest",
      "type": "object"
    }
    ```
