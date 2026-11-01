<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DailyActivity

[All wire models](index.md)

Model aliases: `DailyActivity`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `local_date` | `string` | Yes | Not specified |
| `knowledge` | [`KnowledgeActivityCounts`](knowledgeactivitycounts.md) | Yes | Not specified |
| `mcp_tool_calls` | [`ObservedCount`](observedcount.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### local_date

- Pattern: `"^\\d{4}-\\d{2}-\\d{2}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "local_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "title": "Local Date",
          "type": "string"
        },
        "knowledge": {
          "$ref": "#/$defs/KnowledgeActivityCounts"
        },
        "mcp_tool_calls": {
          "$ref": "#/$defs/ObservedCount"
        }
      },
      "required": [
        "local_date",
        "knowledge",
        "mcp_tool_calls"
      ],
      "title": "DailyActivity",
      "type": "object"
    }
    ```
