<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AssetAvailability

[All wire models](index.md)

Model aliases: `AssetAvailability`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `phase` | `string` | No | `"unknown"` |
| `read` | [`AvailabilityCapability`](availabilitycapability.md) | No | Not specified |
| `search` | [`AvailabilityCapability`](availabilitycapability.md) | No | Not specified |
| `query` | [`AvailabilityCapability`](availabilitycapability.md) | No | Not specified |
| `revision` | [`AvailabilityRevision`](availabilityrevision.md) | No | Not specified |
| `latest_attempt` | [`AvailabilityAttempt`](availabilityattempt.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### phase

- Allowed values: `"unknown"`, `"queued"`, `"processing"`, `"indexing"`, `"complete"`, `"failed"`, `"cancelled"`, `"reconciliation_required"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "phase": {
          "default": "unknown",
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
          "title": "Phase",
          "type": "string"
        },
        "read": {
          "$ref": "#/$defs/AvailabilityCapability"
        },
        "search": {
          "$ref": "#/$defs/AvailabilityCapability"
        },
        "query": {
          "$ref": "#/$defs/AvailabilityCapability"
        },
        "revision": {
          "$ref": "#/$defs/AvailabilityRevision"
        },
        "latest_attempt": {
          "anyOf": [
            {
              "$ref": "#/$defs/AvailabilityAttempt"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "title": "AssetAvailability",
      "type": "object"
    }
    ```
