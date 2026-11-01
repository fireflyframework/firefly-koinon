<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CommunicationUsageSummary

[All wire models](index.md)

Model aliases: `CommunicationUsageSummary`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `scope` | `string` | No | `"own"` |
| `window_start` | `string` | Yes | Not specified |
| `window_end` | `string` | Yes | Not specified |
| `time_zone` | `string` | Yes | Not specified |
| `assistant_runs` | `integer` | Yes | Not specified |
| `completed_runs` | `integer` | Yes | Not specified |
| `failed_runs` | `integer` | Yes | Not specified |
| `mcp_requests` | `integer` or `null` | No | `null` |
| `mcp_request_status` | `string` | No | `"unavailable"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### scope

- Exact value: `"own"`

### window_start

- Format: `"date-time"`

### window_end

- Format: `"date-time"`

### assistant_runs

- Minimum: `0`

### completed_runs

- Minimum: `0`

### failed_runs

- Minimum: `0`

### mcp_requests

- anyOf branch 1 (`integer`): Minimum: `0`

### mcp_request_status

- Allowed values: `"available"`, `"unavailable"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "scope": {
          "const": "own",
          "default": "own",
          "title": "Scope",
          "type": "string"
        },
        "window_start": {
          "format": "date-time",
          "title": "Window Start",
          "type": "string"
        },
        "window_end": {
          "format": "date-time",
          "title": "Window End",
          "type": "string"
        },
        "time_zone": {
          "title": "Time Zone",
          "type": "string"
        },
        "assistant_runs": {
          "minimum": 0,
          "title": "Assistant Runs",
          "type": "integer"
        },
        "completed_runs": {
          "minimum": 0,
          "title": "Completed Runs",
          "type": "integer"
        },
        "failed_runs": {
          "minimum": 0,
          "title": "Failed Runs",
          "type": "integer"
        },
        "mcp_requests": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Mcp Requests"
        },
        "mcp_request_status": {
          "default": "unavailable",
          "enum": [
            "available",
            "unavailable"
          ],
          "title": "Mcp Request Status",
          "type": "string"
        }
      },
      "required": [
        "window_start",
        "window_end",
        "time_zone",
        "assistant_runs",
        "completed_runs",
        "failed_runs"
      ],
      "title": "CommunicationUsageSummary",
      "type": "object"
    }
    ```
