<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentView

[All wire models](index.md)

Model aliases: `AttachmentView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `thread_id` | `string` | Yes | Not specified |
| `filename` | `string` | Yes | Not specified |
| `media_type` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `size_bytes` | `integer` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `page_count` | `integer` or `null` | No | `null` |
| `chunk_count` | `integer` | Yes | Not specified |
| `progress` | [`AttachmentProgress`](attachmentprogress.md) | Yes | Not specified |
| `error_code` | `string` or `null` | No | `null` |
| `error` | `string` or `null` | No | `null` |
| `warnings` | Array of `string` | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"document"`, `"image"`, `"bundle"`

### status

- Allowed values: `"storing"`, `"queued"`, `"extracting"`, `"ready"`, `"failed"`, `"cancelled"`, `"expired"`, `"deleted"`

### created_at

- Format: `"date-time"`

### expires_at

- Format: `"date-time"`


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
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "thread_id": {
          "title": "Thread Id",
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
        "kind": {
          "enum": [
            "document",
            "image",
            "bundle"
          ],
          "title": "Kind",
          "type": "string"
        },
        "size_bytes": {
          "title": "Size Bytes",
          "type": "integer"
        },
        "sha256": {
          "title": "Sha256",
          "type": "string"
        },
        "status": {
          "enum": [
            "storing",
            "queued",
            "extracting",
            "ready",
            "failed",
            "cancelled",
            "expired",
            "deleted"
          ],
          "title": "Status",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
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
        "chunk_count": {
          "title": "Chunk Count",
          "type": "integer"
        },
        "progress": {
          "$ref": "#/$defs/AttachmentProgress"
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Code"
        },
        "error": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error"
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
        "tenant_id",
        "thread_id",
        "filename",
        "media_type",
        "kind",
        "size_bytes",
        "sha256",
        "status",
        "revision",
        "created_at",
        "expires_at",
        "chunk_count",
        "progress"
      ],
      "title": "AttachmentView",
      "type": "object"
    }
    ```
