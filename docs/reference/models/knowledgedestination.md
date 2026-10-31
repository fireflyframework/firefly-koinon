<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeDestination

[All wire models](index.md)

Model aliases: `KnowledgeDestination`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `project_id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `ancestry_digest` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### workspace_id

- Minimum length: `1`
- Maximum length: `64`

### project_id

- Minimum length: `1`
- Maximum length: `64`

### name

- Minimum length: `1`
- Maximum length: `255`

### ancestry_digest

- Pattern: `"^[a-f0-9]{64}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "workspace_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Workspace Id",
          "type": "string"
        },
        "project_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Project Id",
          "type": "string"
        },
        "name": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "ancestry_digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Ancestry Digest",
          "type": "string"
        }
      },
      "required": [
        "id",
        "workspace_id",
        "project_id",
        "name",
        "ancestry_digest"
      ],
      "title": "KnowledgeDestination",
      "type": "object"
    }
    ```
