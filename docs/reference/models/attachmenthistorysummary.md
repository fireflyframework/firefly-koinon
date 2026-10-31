<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentHistorySummary

[All wire models](index.md)

Model aliases: `AttachmentHistorySummary`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `filename` | `string` | Yes | Not specified |
| `media_type` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `size_bytes` | `integer` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `available` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"document"`, `"image"`, `"bundle"`

### status

- Allowed values: `"storing"`, `"queued"`, `"extracting"`, `"ready"`, `"failed"`, `"cancelled"`, `"expired"`, `"deleted"`


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
        "expires_at": {
          "title": "Expires At",
          "type": "string"
        },
        "available": {
          "title": "Available",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "filename",
        "media_type",
        "kind",
        "size_bytes",
        "sha256",
        "status",
        "revision",
        "expires_at",
        "available"
      ],
      "title": "AttachmentHistorySummary",
      "type": "object"
    }
    ```
