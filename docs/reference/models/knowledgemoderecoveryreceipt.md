<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeModeRecoveryReceipt

[All wire models](index.md)

Model aliases: `KnowledgeModeRecoveryReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `index_id` | `string` | Yes | Not specified |
| `job_id` | `string` or `null` | Yes | Not specified |
| `state` | `string` | Yes | Not specified |
| `activation_job_id` | `string` | Yes | Not specified |
| `activation_lease_until` | `string` or `null` | Yes | Not specified |
| `index_status` | `string` | Yes | Not specified |
| `native_pointer_state` | `string` | No | `"unavailable"` |
| `expected_revision` | `integer` or `null` | No | `null` |
| `expected_active_id` | `string` or `null` | No | `null` |
| `expected_connection_revision` | `integer` or `null` | No | `null` |
| `actions` | Array of `string` | Yes | Not specified |
| `message` | `string` | Yes | Not specified |
| `receipt_id` | `string` | Yes | Not specified |
| `attempt_revision` | `integer` | Yes | Not specified |
| `resolution_revision` | `integer` | Yes | Not specified |
| `resolution` | `string` | Yes | Not specified |
| `native_index_id` | `string` | Yes | Not specified |
| `provider_id` | `string` | Yes | Not specified |
| `model_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `native_workspace_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### state

- Allowed values: `"in_progress"`, `"required"`, `"resolved"`

### native_pointer_state

- Allowed values: `"target"`, `"previous"`, `"other"`, `"unavailable"`

### expected_revision

- anyOf branch 1 (`integer`): Minimum: `1`

### expected_connection_revision

- anyOf branch 1 (`integer`): Minimum: `1`

### actions

- Each item: Allowed values: `"finish"`, `"restore_previous"`

### attempt_revision

- Minimum: `1`

### resolution_revision

- Minimum: `1`

### resolution

- Allowed values: `"pending"`, `"finished"`, `"restored"`, `"aborted"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "index_id": {
          "title": "Index Id",
          "type": "string"
        },
        "job_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Job Id"
        },
        "state": {
          "enum": [
            "in_progress",
            "required",
            "resolved"
          ],
          "title": "State",
          "type": "string"
        },
        "activation_job_id": {
          "title": "Activation Job Id",
          "type": "string"
        },
        "activation_lease_until": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Activation Lease Until"
        },
        "index_status": {
          "title": "Index Status",
          "type": "string"
        },
        "native_pointer_state": {
          "default": "unavailable",
          "enum": [
            "target",
            "previous",
            "other",
            "unavailable"
          ],
          "title": "Native Pointer State",
          "type": "string"
        },
        "expected_revision": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Revision"
        },
        "expected_active_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Active Id"
        },
        "expected_connection_revision": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Connection Revision"
        },
        "actions": {
          "items": {
            "enum": [
              "finish",
              "restore_previous"
            ],
            "type": "string"
          },
          "title": "Actions",
          "type": "array"
        },
        "message": {
          "title": "Message",
          "type": "string"
        },
        "receipt_id": {
          "title": "Receipt Id",
          "type": "string"
        },
        "attempt_revision": {
          "minimum": 1,
          "title": "Attempt Revision",
          "type": "integer"
        },
        "resolution_revision": {
          "minimum": 1,
          "title": "Resolution Revision",
          "type": "integer"
        },
        "resolution": {
          "enum": [
            "pending",
            "finished",
            "restored",
            "aborted"
          ],
          "title": "Resolution",
          "type": "string"
        },
        "native_index_id": {
          "title": "Native Index Id",
          "type": "string"
        },
        "provider_id": {
          "title": "Provider Id",
          "type": "string"
        },
        "model_id": {
          "title": "Model Id",
          "type": "string"
        },
        "workspace_id": {
          "title": "Workspace Id",
          "type": "string"
        },
        "native_workspace_id": {
          "title": "Native Workspace Id",
          "type": "string"
        }
      },
      "required": [
        "index_id",
        "job_id",
        "state",
        "activation_job_id",
        "activation_lease_until",
        "index_status",
        "actions",
        "message",
        "receipt_id",
        "attempt_revision",
        "resolution_revision",
        "resolution",
        "native_index_id",
        "provider_id",
        "model_id",
        "workspace_id",
        "native_workspace_id"
      ],
      "title": "KnowledgeModeRecoveryReceipt",
      "type": "object"
    }
    ```
