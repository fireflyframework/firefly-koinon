<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AvailabilityCapability

[All wire models](index.md)

Model aliases: `AvailabilityCapability`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `state` | `string` | No | `"unknown"` |
| `reason` | `string` | No | `"NOT_OBSERVED"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### state

- Allowed values: `"ready"`, `"pending"`, `"unavailable"`, `"unknown"`, `"not_applicable"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "state": {
          "default": "unknown",
          "enum": [
            "ready",
            "pending",
            "unavailable",
            "unknown",
            "not_applicable"
          ],
          "title": "State",
          "type": "string"
        },
        "reason": {
          "default": "NOT_OBSERVED",
          "title": "Reason",
          "type": "string"
        }
      },
      "title": "AvailabilityCapability",
      "type": "object"
    }
    ```
