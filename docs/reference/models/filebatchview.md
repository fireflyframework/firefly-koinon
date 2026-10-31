<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# FileBatchView

[All wire models](index.md)

Model aliases: `FileBatchView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `destination` | [`BulkDestination`](bulkdestination.md) | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `total_items` | `integer` | Yes | Not specified |
| `total_bytes` | `integer` | Yes | Not specified |
| `counts` | Map of string keys to `integer` | Yes | Not specified |
| `cancellation_requested` | `boolean` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"expired"`, `"staging"`, `"queued"`, `"running"`, `"succeeded"`, `"partial"`, `"failed"`, `"cancelled"`, `"reconciling"`

### revision

- Minimum: `1`
- Maximum: `2147483647`

### counts

- Additional properties: `integer`

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
        "destination": {
          "$ref": "#/$defs/BulkDestination"
        },
        "status": {
          "enum": [
            "expired",
            "staging",
            "queued",
            "running",
            "succeeded",
            "partial",
            "failed",
            "cancelled",
            "reconciling"
          ],
          "title": "Status",
          "type": "string"
        },
        "revision": {
          "maximum": 2147483647,
          "minimum": 1,
          "title": "Revision",
          "type": "integer"
        },
        "total_items": {
          "title": "Total Items",
          "type": "integer"
        },
        "total_bytes": {
          "title": "Total Bytes",
          "type": "integer"
        },
        "counts": {
          "additionalProperties": {
            "type": "integer"
          },
          "propertyNames": {
            "enum": [
              "awaiting_upload",
              "staged",
              "queued",
              "running",
              "succeeded",
              "failed",
              "cancelled",
              "reconciling"
            ]
          },
          "title": "Counts",
          "type": "object"
        },
        "cancellation_requested": {
          "title": "Cancellation Requested",
          "type": "boolean"
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
        }
      },
      "required": [
        "id",
        "tenant_id",
        "destination",
        "status",
        "revision",
        "total_items",
        "total_bytes",
        "counts",
        "cancellation_requested",
        "created_at",
        "expires_at"
      ],
      "title": "FileBatchView",
      "type": "object"
    }
    ```
