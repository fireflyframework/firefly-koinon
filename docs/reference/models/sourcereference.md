<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceReference

[All wire models](index.md)

Model aliases: `SourceReference`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `asset_id` | `string` | Yes | Not specified |
| `source_id` | `string` or `null` | No | `null` |
| `title` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `knowledge_item_id` | `string` or `null` | No | `null` |
| `knowledge_version_id` | `string` or `null` | No | `null` |
| `knowledge_version` | `integer` or `null` | No | `null` |
| `source_version_id` | `string` or `null` | No | `null` |
| `extraction_id` | `string` or `null` | No | `null` |
| `source_part_id` | `string` or `null` | No | `null` |
| `source_part_sha256` | `string` or `null` | No | `null` |
| `recorded_page` | `integer` or `null` | No | `null` |
| `page_basis` | `string` or `null` | No | `null` |
| `used_revision` | `string` or `null` | No | `null` |
| `snapshot_id` | `string` or `null` | No | `null` |
| `query_id` | `string` or `null` | No | `null` |
| `chunk_id` | `string` or `null` | No | `null` |
| `page` | `integer` or `null` | No | `null` |
| `section` | `string` or `null` | No | `null` |
| `quote` | `string` or `null` | No | `null` |
| `current_revision` | `string` or `null` | No | `null` |
| `availability` | `string` | No | `"unverified"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### asset_id

- Minimum length: `1`
- Maximum length: `64`

### source_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### title

- Minimum length: `1`
- Maximum length: `255`

### kind

- Allowed values: `"document"`, `"dataset"`, `"knowledge_version"`

### knowledge_item_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### knowledge_version_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### knowledge_version

- anyOf branch 1 (`integer`): Minimum: `1`

### source_version_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### extraction_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### source_part_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### source_part_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### recorded_page

- anyOf branch 1 (`integer`): Minimum: `1`

### page_basis

- anyOf branch 1 (`string`): Exact value: `"recorded_loader"`

### used_revision

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `128`

### snapshot_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### query_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### chunk_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### page

- anyOf branch 1 (`integer`): Minimum: `1`

### section

- anyOf branch 1 (`string`): Maximum length: `512`

### quote

- anyOf branch 1 (`string`): Maximum length: `8000`

### current_revision

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `128`

### availability

- Allowed values: `"available"`, `"changed"`, `"unverified"`


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
        "asset_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Asset Id",
          "type": "string"
        },
        "source_id": {
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
          "title": "Source Id"
        },
        "title": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Title",
          "type": "string"
        },
        "kind": {
          "enum": [
            "document",
            "dataset",
            "knowledge_version"
          ],
          "title": "Kind",
          "type": "string"
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
        "source_part_id": {
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
          "title": "Source Part Id"
        },
        "source_part_sha256": {
          "anyOf": [
            {
              "pattern": "^[a-f0-9]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Part Sha256"
        },
        "recorded_page": {
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
          "title": "Recorded Page"
        },
        "page_basis": {
          "anyOf": [
            {
              "const": "recorded_loader",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page Basis"
        },
        "used_revision": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Used Revision"
        },
        "snapshot_id": {
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
          "title": "Snapshot Id"
        },
        "query_id": {
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
          "title": "Query Id"
        },
        "chunk_id": {
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
          "title": "Chunk Id"
        },
        "page": {
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
          "title": "Page"
        },
        "section": {
          "anyOf": [
            {
              "maxLength": 512,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Section"
        },
        "quote": {
          "anyOf": [
            {
              "maxLength": 8000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Quote"
        },
        "current_revision": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Current Revision"
        },
        "availability": {
          "default": "unverified",
          "enum": [
            "available",
            "changed",
            "unverified"
          ],
          "title": "Availability",
          "type": "string"
        }
      },
      "required": [
        "id",
        "asset_id",
        "title",
        "kind"
      ],
      "title": "SourceReference",
      "type": "object"
    }
    ```
