<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceMappingOutput

[All wire models](index.md)

Model aliases: `SourceMappingOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `policy_revision` | `integer` or `null` | Yes | Not specified |
| `latest_review_revision` | `integer` | Yes | Not specified |
| `control_revision` | `integer` or `null` | Yes | Not specified |
| `connection_id` | `string` | Yes | Not specified |
| `policy` | [`MappingReviewInput`](mappingreviewinput.md) | Yes | Not specified |
| `presentation` | [`SourceMappingPresentation`](sourcemappingpresentation.md) | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `next_run_at` | `string` or `null` | Yes | Not specified |
| `can_pause` | `boolean` | Yes | Not specified |
| `can_resume` | `boolean` | Yes | Not specified |
| `can_retire` | `boolean` | Yes | Not specified |
| `can_sync` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### connection_id

- Minimum length: `1`
- Maximum length: `64`

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
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
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
        "connection_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Connection Id",
          "type": "string"
        },
        "policy": {
          "$ref": "#/$defs/MappingReviewInput"
        },
        "presentation": {
          "$ref": "#/$defs/SourceMappingPresentation"
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
        "can_pause": {
          "title": "Can Pause",
          "type": "boolean"
        },
        "can_resume": {
          "title": "Can Resume",
          "type": "boolean"
        },
        "can_retire": {
          "title": "Can Retire",
          "type": "boolean"
        },
        "can_sync": {
          "title": "Can Sync",
          "type": "boolean"
        }
      },
      "required": [
        "id",
        "revision",
        "policy_revision",
        "latest_review_revision",
        "control_revision",
        "connection_id",
        "policy",
        "presentation",
        "status",
        "next_run_at",
        "can_pause",
        "can_resume",
        "can_retire",
        "can_sync"
      ],
      "title": "SourceMappingOutput",
      "type": "object"
    }
    ```
