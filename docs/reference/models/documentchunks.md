<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentChunks

[All wire models](index.md)

Model aliases: `DocumentChunks`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `document_id` | `string` | Yes | Not specified |
| `source_id` | `string` | Yes | Not specified |
| `native_source_id` | `string` | Yes | Not specified |
| `source_version_id` | `string` or `null` | No | `null` |
| `extraction_id` | `string` or `null` | No | `null` |
| `items` | Array of [`DocumentChunk`](documentchunk.md) | Yes | Not specified |
| `offset` | `integer` | Yes | Not specified |
| `limit` | `integer` | Yes | Not specified |
| `total` | `integer` | Yes | Not specified |
| `next_offset` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "document_id": {
          "title": "Document Id",
          "type": "string"
        },
        "source_id": {
          "title": "Source Id",
          "type": "string"
        },
        "native_source_id": {
          "title": "Native Source Id",
          "type": "string"
        },
        "source_version_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Version Id"
        },
        "extraction_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Extraction Id"
        },
        "items": {
          "items": {
            "$ref": "#/$defs/DocumentChunk"
          },
          "title": "Items",
          "type": "array"
        },
        "offset": {
          "title": "Offset",
          "type": "integer"
        },
        "limit": {
          "title": "Limit",
          "type": "integer"
        },
        "total": {
          "title": "Total",
          "type": "integer"
        },
        "next_offset": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Next Offset"
        }
      },
      "required": [
        "document_id",
        "source_id",
        "native_source_id",
        "items",
        "offset",
        "limit",
        "total"
      ],
      "title": "DocumentChunks",
      "type": "object"
    }
    ```
