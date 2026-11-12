<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceMappingSummary

[All wire models](index.md)

Model aliases: `SourceMappingSummary`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `connection_id` | `string` | Yes | Not specified |
| `policy_revision` | `integer` or `null` | Yes | Not specified |
| `latest_review_revision` | `integer` | Yes | Not specified |
| `control_revision` | `integer` or `null` | Yes | Not specified |
| `next_run_at` | `string` or `null` | Yes | Not specified |
| `presentation` | [`SourceMappingPresentation`](sourcemappingpresentation.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"reviewed"`, `"active"`, `"paused"`, `"reconnect_required"`, `"retired"`

### next_run_at

- anyOf branch 1 (`string`): Format: `"date-time"`


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
        "status": {
          "enum": [
            "reviewed",
            "active",
            "paused",
            "reconnect_required",
            "retired"
          ],
          "title": "Status",
          "type": "string"
        },
        "connection_id": {
          "title": "Connection Id",
          "type": "string"
        },
        "policy_revision": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Policy Revision"
        },
        "latest_review_revision": {
          "title": "Latest Review Revision",
          "type": "integer"
        },
        "control_revision": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Control Revision"
        },
        "next_run_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Next Run At"
        },
        "presentation": {
          "$ref": "#/$defs/SourceMappingPresentation"
        }
      },
      "required": [
        "id",
        "status",
        "connection_id",
        "policy_revision",
        "latest_review_revision",
        "control_revision",
        "next_run_at",
        "presentation"
      ],
      "title": "SourceMappingSummary",
      "type": "object"
    }
    ```
