<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProcessingActivity

[All wire models](index.md)

Model aliases: `ProcessingActivity`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `resource_id` | `string` | Yes | Not specified |
| `operation` | `string` | Yes | Not specified |
| `state` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |
| `availability` | [`AssetAvailability`](assetavailability.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### state

- Allowed values: `"unknown"`, `"queued"`, `"processing"`, `"indexing"`, `"complete"`, `"failed"`, `"cancelled"`, `"reconciliation_required"`

### updated_at

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
        "resource_id": {
          "title": "Resource Id",
          "type": "string"
        },
        "operation": {
          "title": "Operation",
          "type": "string"
        },
        "state": {
          "enum": [
            "unknown",
            "queued",
            "processing",
            "indexing",
            "complete",
            "failed",
            "cancelled",
            "reconciliation_required"
          ],
          "title": "State",
          "type": "string"
        },
        "updated_at": {
          "format": "date-time",
          "title": "Updated At",
          "type": "string"
        },
        "availability": {
          "$ref": "#/$defs/AssetAvailability"
        }
      },
      "required": [
        "id",
        "resource_id",
        "operation",
        "state",
        "updated_at",
        "availability"
      ],
      "title": "ProcessingActivity",
      "type": "object"
    }
    ```
