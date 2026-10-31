<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OperationalLimits

[All wire models](index.md)

Model aliases: `OperationalLimits`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `worker_concurrency` | `integer` | Yes | Not specified |
| `max_queued_per_subject` | `integer` | Yes | Not specified |
| `job_lease_seconds` | `integer` | Yes | Not specified |
| `max_index_workspaces` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "worker_concurrency": {
          "title": "Worker Concurrency",
          "type": "integer"
        },
        "max_queued_per_subject": {
          "title": "Max Queued Per Subject",
          "type": "integer"
        },
        "job_lease_seconds": {
          "title": "Job Lease Seconds",
          "type": "integer"
        },
        "max_index_workspaces": {
          "title": "Max Index Workspaces",
          "type": "integer"
        }
      },
      "required": [
        "worker_concurrency",
        "max_queued_per_subject",
        "job_lease_seconds",
        "max_index_workspaces"
      ],
      "title": "OperationalLimits",
      "type": "object"
    }
    ```
