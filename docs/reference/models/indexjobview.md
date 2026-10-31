<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IndexJobView

[All wire models](index.md)

Model aliases: `IndexJobView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `index` | [`KnowledgeIndexView`](knowledgeindexview.md) | Yes | Not specified |
| `job_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "index": {
          "$ref": "#/$defs/KnowledgeIndexView"
        },
        "job_id": {
          "title": "Job Id",
          "type": "string"
        }
      },
      "required": [
        "index",
        "job_id"
      ],
      "title": "IndexJobView",
      "type": "object"
    }
    ```
