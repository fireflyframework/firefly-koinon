<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ActivitySummary

[All wire models](index.md)

Model aliases: `ActivitySummary`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `audience` | `string` | Yes | Not specified |
| `window` | [`ActivityWindow`](activitywindow.md) | Yes | Not specified |
| `coverage` | [`ActivityCoverage`](activitycoverage.md) | Yes | Not specified |
| `knowledge` | [`KnowledgeActivityCounts`](knowledgeactivitycounts.md) | Yes | Not specified |
| `top_projects` | Array of [`ProjectActivity`](projectactivity.md) | No | Not specified |
| `daily_activity` | Array of [`DailyActivity`](dailyactivity.md) | No | Not specified |
| `mcp` | [`McpActivityCounts`](mcpactivitycounts.md) | Yes | Not specified |
| `models` | [`ModelActivityCounts`](modelactivitycounts.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### audience

- Allowed values: `"personal"`, `"organization_administrators"`

### top_projects

- Maximum items: `10`

### daily_activity

- Maximum items: `367`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "audience": {
          "enum": [
            "personal",
            "organization_administrators"
          ],
          "title": "Audience",
          "type": "string"
        },
        "window": {
          "$ref": "#/$defs/ActivityWindow"
        },
        "coverage": {
          "$ref": "#/$defs/ActivityCoverage"
        },
        "knowledge": {
          "$ref": "#/$defs/KnowledgeActivityCounts"
        },
        "top_projects": {
          "items": {
            "$ref": "#/$defs/ProjectActivity"
          },
          "maxItems": 10,
          "title": "Top Projects",
          "type": "array"
        },
        "daily_activity": {
          "items": {
            "$ref": "#/$defs/DailyActivity"
          },
          "maxItems": 367,
          "title": "Daily Activity",
          "type": "array"
        },
        "mcp": {
          "$ref": "#/$defs/McpActivityCounts"
        },
        "models": {
          "$ref": "#/$defs/ModelActivityCounts"
        }
      },
      "required": [
        "tenant_id",
        "audience",
        "window",
        "coverage",
        "knowledge",
        "mcp",
        "models"
      ],
      "title": "ActivitySummary",
      "type": "object"
    }
    ```
