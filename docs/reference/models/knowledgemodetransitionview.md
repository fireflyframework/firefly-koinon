<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeModeTransitionView

[All wire models](index.md)

Model aliases: `KnowledgeModeTransitionView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `job_id` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `base_revision` | `integer` | Yes | Not specified |
| `base_digest` | `string` | Yes | Not specified |
| `active_mode` | `string` | Yes | Not specified |
| `requested_mode` | `string` | Yes | Not specified |
| `requested_settings` | [`OrganizationKnowledgeSettingsInput`](organizationknowledgesettingsinput.md) | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `stage` | `string` | Yes | Not specified |
| `counters` | Map of string keys to `integer` | Yes | Not specified |
| `stage_milliseconds` | Map of string keys to `integer` | Yes | Not specified |
| `pending_index_recoveries` | `integer` | No | `0` |
| `progress_reason` | `string` or `null` | No | `null` |
| `error_code` | `string` or `null` | Yes | Not specified |
| `error` | `string` or `null` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### revision

- Minimum: `1`

### base_revision

- Minimum: `0`

### base_digest

- Pattern: `"^[a-f0-9]{64}$"`

### active_mode

- Allowed values: `"rag"`, `"rlm"`

### requested_mode

- Allowed values: `"rag"`, `"rlm"`

### status

- Allowed values: `"queued"`, `"running"`, `"failed"`, `"cancelled"`, `"superseded"`, `"succeeded"`

### stage

- Allowed values: `"discovery"`, `"preflight"`, `"repair_views"`, `"prepare_indexes"`, `"verify"`, `"activate"`

### counters

- Additional properties: `integer`

### stage_milliseconds

- Additional properties: `integer`

### pending_index_recoveries

- Minimum: `0`

### progress_reason

- anyOf branch 1 (`string`): Exact value: `"knowledge_changed"`


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
        "job_id": {
          "title": "Job Id",
          "type": "string"
        },
        "revision": {
          "minimum": 1,
          "title": "Revision",
          "type": "integer"
        },
        "base_revision": {
          "minimum": 0,
          "title": "Base Revision",
          "type": "integer"
        },
        "base_digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Base Digest",
          "type": "string"
        },
        "active_mode": {
          "enum": [
            "rag",
            "rlm"
          ],
          "title": "Active Mode",
          "type": "string"
        },
        "requested_mode": {
          "enum": [
            "rag",
            "rlm"
          ],
          "title": "Requested Mode",
          "type": "string"
        },
        "requested_settings": {
          "$ref": "#/$defs/OrganizationKnowledgeSettingsInput"
        },
        "status": {
          "enum": [
            "queued",
            "running",
            "failed",
            "cancelled",
            "superseded",
            "succeeded"
          ],
          "title": "Status",
          "type": "string"
        },
        "stage": {
          "enum": [
            "discovery",
            "preflight",
            "repair_views",
            "prepare_indexes",
            "verify",
            "activate"
          ],
          "title": "Stage",
          "type": "string"
        },
        "counters": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Counters",
          "type": "object"
        },
        "stage_milliseconds": {
          "additionalProperties": {
            "type": "integer"
          },
          "title": "Stage Milliseconds",
          "type": "object"
        },
        "pending_index_recoveries": {
          "default": 0,
          "minimum": 0,
          "title": "Pending Index Recoveries",
          "type": "integer"
        },
        "progress_reason": {
          "anyOf": [
            {
              "const": "knowledge_changed",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Progress Reason"
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Error Code"
        },
        "error": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Error"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "updated_at": {
          "title": "Updated At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "job_id",
        "revision",
        "base_revision",
        "base_digest",
        "active_mode",
        "requested_mode",
        "requested_settings",
        "status",
        "stage",
        "counters",
        "stage_milliseconds",
        "error_code",
        "error",
        "created_at",
        "updated_at"
      ],
      "title": "KnowledgeModeTransitionView",
      "type": "object"
    }
    ```
