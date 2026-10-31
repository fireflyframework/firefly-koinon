<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentEvidenceItem

[All wire models](index.md)

Model aliases: `AttachmentEvidenceItem`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `filename` | `string` | Yes | Not specified |
| `media_type` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `complete` | `boolean` | Yes | Not specified |
| `chunk_ids` | Array of `string` | Yes | Not specified |
| `total_chunks` | `integer` | Yes | Not specified |
| `warnings` | Array of `string` | Yes | Not specified |

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
        "filename": {
          "title": "Filename",
          "type": "string"
        },
        "media_type": {
          "title": "Media Type",
          "type": "string"
        },
        "sha256": {
          "title": "Sha256",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "complete": {
          "title": "Complete",
          "type": "boolean"
        },
        "chunk_ids": {
          "items": {
            "type": "string"
          },
          "title": "Chunk Ids",
          "type": "array"
        },
        "total_chunks": {
          "title": "Total Chunks",
          "type": "integer"
        },
        "warnings": {
          "items": {
            "type": "string"
          },
          "title": "Warnings",
          "type": "array"
        }
      },
      "required": [
        "id",
        "filename",
        "media_type",
        "sha256",
        "revision",
        "complete",
        "chunk_ids",
        "total_chunks",
        "warnings"
      ],
      "title": "AttachmentEvidenceItem",
      "type": "object"
    }
    ```
