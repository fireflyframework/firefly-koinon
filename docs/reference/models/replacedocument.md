<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ReplaceDocument

[All wire models](index.md)

Model aliases: `ReplaceDocument`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_source_version_id` | `string` or `null` | No | `null` |
| `expected_extraction_id` | `string` or `null` | No | `null` |
| `expected_revision` | `integer` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |
| `document_id` | `string` | Yes | Not specified |
| `expected_sha256` | `string` | Yes | Not specified |
| `acknowledge_chunk_invalidation` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_source_version_id

- anyOf branch 1 (`string`): Format: `"uuid"`

### expected_extraction_id

- anyOf branch 1 (`string`): Format: `"uuid"`

### expected_revision

- Minimum: `1`

### action

- Exact value: `"replace_document"`

### document_id

- Minimum length: `1`
- Maximum length: `64`

### expected_sha256

- Pattern: `"^[a-fA-F0-9]{64}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_source_version_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Source Version Id"
        },
        "expected_extraction_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Extraction Id"
        },
        "expected_revision": {
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        },
        "action": {
          "const": "replace_document",
          "title": "Action",
          "type": "string"
        },
        "document_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Document Id",
          "type": "string"
        },
        "expected_sha256": {
          "pattern": "^[a-fA-F0-9]{64}$",
          "title": "Expected Sha256",
          "type": "string"
        },
        "acknowledge_chunk_invalidation": {
          "title": "Acknowledge Chunk Invalidation",
          "type": "boolean"
        }
      },
      "required": [
        "expected_revision",
        "action",
        "document_id",
        "expected_sha256",
        "acknowledge_chunk_invalidation"
      ],
      "title": "ReplaceDocument",
      "type": "object"
    }
    ```
