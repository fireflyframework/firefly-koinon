<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeItemSummary

[All wire models](index.md)

Model aliases: `KnowledgeItemSummary`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `project_id` | `string` | Yes | Not specified |
| `destination_id` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `summary` | `string` | Yes | Not specified |
| `head_version` | `integer` | Yes | Not specified |
| `serving_version` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### workspace_id

- Minimum length: `1`
- Maximum length: `64`

### project_id

- Minimum length: `1`
- Maximum length: `64`

### destination_id

- Minimum length: `1`
- Maximum length: `64`

### title

- Minimum length: `1`
- Maximum length: `255`

### summary

- Maximum length: `4000`

### head_version

- Minimum: `1`

### serving_version

- anyOf branch 1 (`integer`): Minimum: `1`


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
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
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
        "destination_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Destination Id",
          "type": "string"
        },
        "title": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Title",
          "type": "string"
        },
        "summary": {
          "maxLength": 4000,
          "title": "Summary",
          "type": "string"
        },
        "head_version": {
          "minimum": 1,
          "title": "Head Version",
          "type": "integer"
        },
        "serving_version": {
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
          "title": "Serving Version"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "workspace_id",
        "project_id",
        "destination_id",
        "title",
        "summary",
        "head_version"
      ],
      "title": "KnowledgeItemSummary",
      "type": "object"
    }
    ```
