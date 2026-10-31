<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentPromotionRequirements

[All wire models](index.md)

Model aliases: `AttachmentPromotionRequirements`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `ready_attachment` | `boolean` | No | `true` |
| `ingest_write` | `boolean` | No | `true` |
| `catalog_write` | `boolean` | No | `true` |
| `document_sha256` | `boolean` | No | `true` |
| `document_chunk_invalidation_acknowledgement` | `boolean` | No | `true` |
| `table_snapshot_id` | `boolean` | No | `true` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "ready_attachment": {
          "default": true,
          "title": "Ready Attachment",
          "type": "boolean"
        },
        "ingest_write": {
          "default": true,
          "title": "Ingest Write",
          "type": "boolean"
        },
        "catalog_write": {
          "default": true,
          "title": "Catalog Write",
          "type": "boolean"
        },
        "document_sha256": {
          "default": true,
          "title": "Document Sha256",
          "type": "boolean"
        },
        "document_chunk_invalidation_acknowledgement": {
          "default": true,
          "title": "Document Chunk Invalidation Acknowledgement",
          "type": "boolean"
        },
        "table_snapshot_id": {
          "default": true,
          "title": "Table Snapshot Id",
          "type": "boolean"
        }
      },
      "title": "AttachmentPromotionRequirements",
      "type": "object"
    }
    ```
