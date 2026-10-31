<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NativeReadReceipt

[All wire models](index.md)

Model aliases: `NativeReadReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `result_id` | `string` | Yes | Not specified |
| `generation_id` | `string` or `null` | No | `null` |
| `stage` | `string` | Yes | Not specified |
| `domain` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `entity_id` | `string` | Yes | Not specified |
| `content_sha256` | `string` | Yes | Not specified |
| `source_ids` | Array of `string` | No | Not specified |
| `snapshot_ids` | Array of `string` | No | Not specified |
| `engine` | `string` or `null` | No | `null` |
| `database` | `string` or `null` | No | `null` |
| `catalog` | `string` or `null` | No | `null` |
| `schema` | `string` or `null` | No | `null` |
| `read_kind` | `string` or `null` | No | `null` |
| `origin` | [`NativeReadOrigin`](nativereadorigin.md) or `null` | No | `null` |
| `source_version_id` | `string` or `null` | No | `null` |
| `extraction_id` | `string` or `null` | No | `null` |
| `knowledge_item_id` | `string` or `null` | No | `null` |
| `knowledge_version_id` | `string` or `null` | No | `null` |
| `knowledge_version` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### result_id

- Minimum length: `1`
- Maximum length: `64`

### stage

- Minimum length: `1`
- Maximum length: `64`

### domain

- Allowed values: `"documents"`, `"structured"`, `"knowledge"`

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### workspace_id

- Minimum length: `1`
- Maximum length: `64`

### entity_id

- Minimum length: `1`
- Maximum length: `64`

### content_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### source_ids

- Maximum items: `500`

### snapshot_ids

- Maximum items: `500`

### engine

- anyOf branch 1 (`string`): Maximum length: `64`

### database

- anyOf branch 1 (`string`): Maximum length: `255`

### catalog

- anyOf branch 1 (`string`): Maximum length: `255`

### schema

- anyOf branch 1 (`string`): Maximum length: `255`

### read_kind

- anyOf branch 1 (`string`): Allowed values: `"indexed_document"`, `"metadata"`, `"document_extraction"`, `"knowledge_version"`

### source_version_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### extraction_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### knowledge_item_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### knowledge_version_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### knowledge_version

- anyOf branch 1 (`integer`): Minimum: `1`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "result_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Result Id",
          "type": "string"
        },
        "generation_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Generation Id"
        },
        "stage": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Stage",
          "type": "string"
        },
        "domain": {
          "enum": [
            "documents",
            "structured",
            "knowledge"
          ],
          "title": "Domain",
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
        "entity_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Entity Id",
          "type": "string"
        },
        "content_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Content Sha256",
          "type": "string"
        },
        "source_ids": {
          "items": {
            "type": "string"
          },
          "maxItems": 500,
          "title": "Source Ids",
          "type": "array"
        },
        "snapshot_ids": {
          "items": {
            "type": "string"
          },
          "maxItems": 500,
          "title": "Snapshot Ids",
          "type": "array"
        },
        "engine": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Engine"
        },
        "database": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Database"
        },
        "catalog": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Catalog"
        },
        "schema": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Schema"
        },
        "read_kind": {
          "anyOf": [
            {
              "enum": [
                "indexed_document",
                "metadata",
                "document_extraction",
                "knowledge_version"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Read Kind"
        },
        "origin": {
          "anyOf": [
            {
              "$ref": "#/$defs/NativeReadOrigin"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "source_version_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Version Id"
        },
        "extraction_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Extraction Id"
        },
        "knowledge_item_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Knowledge Item Id"
        },
        "knowledge_version_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Knowledge Version Id"
        },
        "knowledge_version": {
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
          "title": "Knowledge Version"
        }
      },
      "required": [
        "result_id",
        "stage",
        "domain",
        "tenant_id",
        "workspace_id",
        "entity_id",
        "content_sha256"
      ],
      "title": "NativeReadReceipt",
      "type": "object"
    }
    ```
