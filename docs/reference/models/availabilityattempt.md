<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AvailabilityAttempt

[All wire models](index.md)

Model aliases: `AvailabilityAttempt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `operation` | `string` | Yes | Not specified |
| `state` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### state

- Allowed values: `"unknown"`, `"queued"`, `"processing"`, `"indexing"`, `"complete"`, `"failed"`, `"cancelled"`, `"reconciliation_required"`


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
        }
      },
      "required": [
        "id",
        "operation",
        "state"
      ],
      "title": "AvailabilityAttempt",
      "type": "object"
    }
    ```
