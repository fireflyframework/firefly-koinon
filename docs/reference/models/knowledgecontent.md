<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeContent

[All wire models](index.md)

Model aliases: `KnowledgeContent`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `title` | `string` | Yes | Not specified |
| `body` | `string` | Yes | Not specified |
| `summary` | `string` or `null` | No | `null` |
| `domain` | `string` | No | `"other"` |
| `tags` | Array of `string` | No | `[]` |

## Model constraints

- Additional properties: permitted

## Field constraints

### title

- Minimum length: `1`
- Maximum length: `255`

### body

- Minimum length: `1`
- Maximum length: `262144`

### summary

- anyOf branch 1 (`string`): Maximum length: `4000`

### domain

- Allowed values: `"legal"`, `"compliance"`, `"process"`, `"network"`, `"ai_platform"`, `"executive"`, `"hr"`, `"cto"`, `"engineering"`, `"security"`, `"other"`

### tags

- Maximum items: `64`
- Each item: Minimum length: `1`
- Each item: Maximum length: `128`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "title": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Title",
          "type": "string"
        },
        "body": {
          "maxLength": 262144,
          "minLength": 1,
          "title": "Body",
          "type": "string"
        },
        "summary": {
          "anyOf": [
            {
              "maxLength": 4000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Summary"
        },
        "domain": {
          "default": "other",
          "enum": [
            "legal",
            "compliance",
            "process",
            "network",
            "ai_platform",
            "executive",
            "hr",
            "cto",
            "engineering",
            "security",
            "other"
          ],
          "title": "Domain",
          "type": "string"
        },
        "tags": {
          "default": [],
          "items": {
            "maxLength": 128,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 64,
          "title": "Tags",
          "type": "array"
        }
      },
      "required": [
        "title",
        "body"
      ],
      "title": "KnowledgeContent",
      "type": "object"
    }
    ```
