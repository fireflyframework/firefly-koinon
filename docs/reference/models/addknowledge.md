<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AddKnowledge

[All wire models](index.md)

Model aliases: `AddKnowledge`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |
| `mode` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `project_id` | `string` | Yes | Not specified |
| `parent_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`

### action

- Exact value: `"add"`

### mode

- Allowed values: `"document"`, `"dataset"`

### workspace_id

- Minimum length: `1`
- Maximum length: `64`

### project_id

- Minimum length: `1`
- Maximum length: `64`

### parent_id

- Minimum length: `1`
- Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        },
        "action": {
          "const": "add",
          "title": "Action",
          "type": "string"
        },
        "mode": {
          "enum": [
            "document",
            "dataset"
          ],
          "title": "Mode",
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
        "parent_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Parent Id",
          "type": "string"
        }
      },
      "required": [
        "expected_revision",
        "action",
        "mode",
        "workspace_id",
        "project_id",
        "parent_id"
      ],
      "title": "AddKnowledge",
      "type": "object"
    }
    ```
