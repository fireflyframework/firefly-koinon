<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProjectActivity

[All wire models](index.md)

Model aliases: `ProjectActivity`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `project_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `knowledge` | [`KnowledgeActivityCounts`](knowledgeactivitycounts.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### project_id

- Minimum length: `1`
- Maximum length: `64`

### workspace_id

- Minimum length: `1`
- Maximum length: `64`

### name

- Minimum length: `1`
- Maximum length: `255`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "project_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Project Id",
          "type": "string"
        },
        "workspace_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Workspace Id",
          "type": "string"
        },
        "name": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "knowledge": {
          "$ref": "#/$defs/KnowledgeActivityCounts"
        }
      },
      "required": [
        "project_id",
        "workspace_id",
        "name",
        "knowledge"
      ],
      "title": "ProjectActivity",
      "type": "object"
    }
    ```
