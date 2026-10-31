<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationKnowledgeSnapshot

[All wire models](index.md)

Model aliases: `OrganizationKnowledgeSnapshot`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `schema_version` | `integer` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `origin` | `string` | Yes | Not specified |
| `documents` | [`DocumentKnowledgeSettings`](documentknowledgesettings.md) | Yes | Not specified |
| `structured` | [`StructuredKnowledgeSettings`](structuredknowledgesettings.md) | Yes | Not specified |
| `digest` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### schema_version

- Exact value: `1`

### revision

- Minimum: `0`
- Maximum: `2147483647`

### origin

- Allowed values: `"deployment"`, `"organization"`

### digest

- Pattern: `"^[a-f0-9]{64}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "schema_version": {
          "const": 1,
          "title": "Schema Version",
          "type": "integer"
        },
        "revision": {
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Revision",
          "type": "integer"
        },
        "origin": {
          "enum": [
            "deployment",
            "organization"
          ],
          "title": "Origin",
          "type": "string"
        },
        "documents": {
          "$ref": "#/$defs/DocumentKnowledgeSettings"
        },
        "structured": {
          "$ref": "#/$defs/StructuredKnowledgeSettings"
        },
        "digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Digest",
          "type": "string"
        }
      },
      "required": [
        "tenant_id",
        "schema_version",
        "revision",
        "origin",
        "documents",
        "structured",
        "digest"
      ],
      "title": "OrganizationKnowledgeSnapshot",
      "type": "object"
    }
    ```
