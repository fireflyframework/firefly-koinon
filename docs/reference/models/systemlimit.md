<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SystemLimit

[All wire models](index.md)

Model aliases: `SystemLimit`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `value` | `integer` | Yes | Not specified |
| `unit` | `string` | Yes | Not specified |
| `scope` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Allowed values: `"api_capacity"`, `"worker_capacity"`, `"worker_concurrency"`, `"max_index_workspaces"`, `"mcp_max_concurrency"`, `"mcp_max_request_bytes"`, `"mcp_max_response_bytes"`, `"ingestion_raw_max_bytes"`, `"ingestion_scratch_max_bytes"`, `"ingestion_child_rss_max_bytes"`

### value

- Minimum: `0`
- Maximum: `9007199254740991`

### unit

- Allowed values: `"operations"`, `"bytes"`, `"workspaces"`

### scope

- Allowed values: `"process"`, `"file"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "enum": [
            "api_capacity",
            "worker_capacity",
            "worker_concurrency",
            "max_index_workspaces",
            "mcp_max_concurrency",
            "mcp_max_request_bytes",
            "mcp_max_response_bytes",
            "ingestion_raw_max_bytes",
            "ingestion_scratch_max_bytes",
            "ingestion_child_rss_max_bytes"
          ],
          "title": "Id",
          "type": "string"
        },
        "value": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Value",
          "type": "integer"
        },
        "unit": {
          "enum": [
            "operations",
            "bytes",
            "workspaces"
          ],
          "title": "Unit",
          "type": "string"
        },
        "scope": {
          "enum": [
            "process",
            "file"
          ],
          "title": "Scope",
          "type": "string"
        }
      },
      "required": [
        "id",
        "value",
        "unit",
        "scope"
      ],
      "title": "SystemLimit",
      "type": "object"
    }
    ```
