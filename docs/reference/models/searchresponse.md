<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SearchResponse

[All wire models](index.md)

Model aliases: `SearchResponse`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `knowledge_settings_snapshot` | [`OrganizationKnowledgeSnapshot`](organizationknowledgesnapshot.md) or `null` | No | `null` |
| `hits` | Array of [`SearchHit`](searchhit.md) | Yes | Not specified |
| `answer` | `string` or `null` | No | `null` |
| `citations` | Array of [`Citation`](citation.md) | No | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "knowledge_settings_snapshot": {
          "anyOf": [
            {
              "$ref": "#/$defs/OrganizationKnowledgeSnapshot"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "hits": {
          "items": {
            "$ref": "#/$defs/SearchHit"
          },
          "title": "Hits",
          "type": "array"
        },
        "answer": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Answer"
        },
        "citations": {
          "items": {
            "$ref": "#/$defs/Citation"
          },
          "title": "Citations",
          "type": "array"
        }
      },
      "required": [
        "hits"
      ],
      "title": "SearchResponse",
      "type": "object"
    }
    ```
