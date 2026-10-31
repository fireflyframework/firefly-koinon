<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CorporateProfileRefresh

[All wire models](index.md)

Model aliases: `CorporateProfileRefresh`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `profile_id` | `string` or `null` | No | `null` |
| `status` | `string` | Yes | Not specified |
| `snapshot_revision` | `integer` | No | `0` |
| `last_synced_at` | `string` or `null` | No | `null` |
| `last_attempt_at` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"not_configured"`, `"not_bound"`, `"queued"`, `"running"`, `"current"`, `"stale"`, `"unavailable"`, `"conflict"`

### snapshot_revision

- Minimum: `0`
- Maximum: `2147483647`

### last_synced_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### last_attempt_at

- anyOf branch 1 (`string`): Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "profile_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Profile Id"
        },
        "status": {
          "enum": [
            "not_configured",
            "not_bound",
            "queued",
            "running",
            "current",
            "stale",
            "unavailable",
            "conflict"
          ],
          "title": "Status",
          "type": "string"
        },
        "snapshot_revision": {
          "default": 0,
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Snapshot Revision",
          "type": "integer"
        },
        "last_synced_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Synced At"
        },
        "last_attempt_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Last Attempt At"
        }
      },
      "required": [
        "tenant_id",
        "status"
      ],
      "title": "CorporateProfileRefresh",
      "type": "object"
    }
    ```
