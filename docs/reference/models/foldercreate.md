<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# FolderCreate

[All wire models](index.md)

Model aliases: `FolderCreate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Not specified |
| `parent_id` | `string` or `null` | No | `null` |
| `scope` | [`KnowledgeScope`](knowledgescope.md) or `null` | No | `null` |
| `memory_enabled` | `boolean` | No | `false` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### name

- Minimum length: `1`
- Maximum length: `120`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "parent_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Id"
        },
        "scope": {
          "anyOf": [
            {
              "$ref": "#/$defs/KnowledgeScope"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "memory_enabled": {
          "default": false,
          "title": "Memory Enabled",
          "type": "boolean"
        }
      },
      "required": [
        "name"
      ],
      "title": "FolderCreate",
      "type": "object"
    }
    ```
