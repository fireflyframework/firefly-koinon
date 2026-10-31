<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SearchHit

[All wire models](index.md)

Model aliases: `SearchHit`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `text` | `string` | Yes | Not specified |
| `asset_id` | `string` | Yes | Not specified |
| `source_id` | `string` or `null` | No | `null` |
| `score` | `number` or `null` | No | `null` |
| `source_reference` | [`SourceReference`](sourcereference.md) or `null` | No | `null` |
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
        "id": {
          "title": "Id",
          "type": "string"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "text": {
          "title": "Text",
          "type": "string"
        },
        "asset_id": {
          "title": "Asset Id",
          "type": "string"
        },
        "source_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Id"
        },
        "score": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Score"
        },
        "source_reference": {
          "anyOf": [
            {
              "$ref": "#/$defs/SourceReference"
            },
            {
              "type": "null"
            }
          ],
          "default": null
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
        "id",
        "title",
        "text",
        "asset_id"
      ],
      "title": "SearchHit",
      "type": "object"
    }
    ```
