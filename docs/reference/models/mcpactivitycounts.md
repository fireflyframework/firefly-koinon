<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpActivityCounts

[All wire models](index.md)

Model aliases: `McpActivityCounts`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `requests` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `tool_calls` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `succeeded` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `failed` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `rejected` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `average_duration_ms` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `p95_duration_ms` | [`ObservedCount`](observedcount.md) | Yes | Not specified |
| `tool_cancelled` | [`ObservedCount`](observedcount.md) | No | Not specified |
| `request_succeeded` | [`ObservedCount`](observedcount.md) | No | Not specified |
| `request_failed` | [`ObservedCount`](observedcount.md) | No | Not specified |
| `request_rejected` | [`ObservedCount`](observedcount.md) | No | Not specified |
| `request_cancelled` | [`ObservedCount`](observedcount.md) | No | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "requests": {
          "$ref": "#/$defs/ObservedCount"
        },
        "tool_calls": {
          "$ref": "#/$defs/ObservedCount"
        },
        "succeeded": {
          "$ref": "#/$defs/ObservedCount"
        },
        "failed": {
          "$ref": "#/$defs/ObservedCount"
        },
        "rejected": {
          "$ref": "#/$defs/ObservedCount"
        },
        "average_duration_ms": {
          "$ref": "#/$defs/ObservedCount"
        },
        "p95_duration_ms": {
          "$ref": "#/$defs/ObservedCount"
        },
        "tool_cancelled": {
          "$ref": "#/$defs/ObservedCount"
        },
        "request_succeeded": {
          "$ref": "#/$defs/ObservedCount"
        },
        "request_failed": {
          "$ref": "#/$defs/ObservedCount"
        },
        "request_rejected": {
          "$ref": "#/$defs/ObservedCount"
        },
        "request_cancelled": {
          "$ref": "#/$defs/ObservedCount"
        }
      },
      "required": [
        "requests",
        "tool_calls",
        "succeeded",
        "failed",
        "rejected",
        "average_duration_ms",
        "p95_duration_ms"
      ],
      "title": "McpActivityCounts",
      "type": "object"
    }
    ```
