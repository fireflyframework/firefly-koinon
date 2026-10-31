<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MetricsObservation

[All wire models](index.md)

Model aliases: `MetricsObservation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `configured` | `boolean` | Yes | Not specified |
| `available` | `boolean` or `null` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `observed_at` | `string` | Yes | Not specified |
| `reason` | `string` | Yes | Not specified |
| `exporter_configured` | `boolean` or `null` | No | `null` |
| `names` | Array of `string` | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"passed"`, `"failed"`, `"unknown"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "configured": {
          "title": "Configured",
          "type": "boolean"
        },
        "available": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "title": "Available"
        },
        "status": {
          "enum": [
            "passed",
            "failed",
            "unknown"
          ],
          "title": "Status",
          "type": "string"
        },
        "observed_at": {
          "title": "Observed At",
          "type": "string"
        },
        "reason": {
          "title": "Reason",
          "type": "string"
        },
        "exporter_configured": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Exporter Configured"
        },
        "names": {
          "items": {
            "type": "string"
          },
          "title": "Names",
          "type": "array"
        }
      },
      "required": [
        "configured",
        "available",
        "status",
        "observed_at",
        "reason"
      ],
      "title": "MetricsObservation",
      "type": "object"
    }
    ```
