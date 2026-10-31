<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GlossaryTermRead

[All wire models](index.md)

Model aliases: `GlossaryTermRead`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `term` | `string` | Yes | Not specified |
| `definition` | `string` | Yes | Not specified |
| `synonyms_json` | Array of `string` | Yes | Not specified |
| `tags_json` | Array of `string` | Yes | Not specified |
| `related_columns_json` | Array of `string` | Yes | Not specified |
| `related_metrics_json` | Array of `string` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "workspace_id": {
          "title": "Workspace Id",
          "type": "string"
        },
        "term": {
          "title": "Term",
          "type": "string"
        },
        "definition": {
          "title": "Definition",
          "type": "string"
        },
        "synonyms_json": {
          "items": {
            "type": "string"
          },
          "title": "Synonyms Json",
          "type": "array"
        },
        "tags_json": {
          "items": {
            "type": "string"
          },
          "title": "Tags Json",
          "type": "array"
        },
        "related_columns_json": {
          "items": {
            "type": "string"
          },
          "title": "Related Columns Json",
          "type": "array"
        },
        "related_metrics_json": {
          "items": {
            "type": "string"
          },
          "title": "Related Metrics Json",
          "type": "array"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "updated_at": {
          "title": "Updated At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "workspace_id",
        "term",
        "definition",
        "synonyms_json",
        "tags_json",
        "related_columns_json",
        "related_metrics_json",
        "created_at",
        "updated_at"
      ],
      "title": "GlossaryTermRead",
      "type": "object"
    }
    ```
