<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryBatchView

[All wire models](index.md)

Model aliases: `QueryBatchView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `total_items` | `integer` | Yes | Not specified |
| `counts` | Map of string keys to `integer` | Yes | Not specified |
| `cancellation_requested` | `boolean` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"queued"`, `"running"`, `"succeeded"`, `"partial"`, `"failed"`, `"cancelled"`, `"reconciling"`

### revision

- Minimum: `1`
- Maximum: `2147483647`

### total_items

- Minimum: `1`
- Maximum: `20`

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
        "workspace_id": {
          "title": "Workspace Id",
          "type": "string"
        },
        "status": {
          "enum": [
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
          "maximum": 20,
          "minimum": 1,
          "title": "Total Items",
          "type": "integer"
        },
        "counts": {
          "additionalProperties": {
            "type": "integer"
          },
          "propertyNames": {
            "enum": [
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
        "workspace_id",
        "status",
        "revision",
        "total_items",
        "counts",
        "cancellation_requested",
        "created_at",
        "expires_at"
      ],
      "title": "QueryBatchView",
      "type": "object"
    }
    ```
