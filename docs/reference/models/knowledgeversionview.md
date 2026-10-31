<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeVersionView

[All wire models](index.md)

Model aliases: `KnowledgeVersionView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `item_id` | `string` | Yes | Not specified |
| `version` | `integer` | Yes | Not specified |
| `version_id` | `string` | Yes | Not specified |
| `publication` | `string` | Yes | Not specified |
| `serving` | `boolean` | Yes | Not specified |
| `content` | [`KnowledgeContent`](knowledgecontent.md) | Yes | Not specified |
| `evidence` | Array of [`UserStatementEvidence`](userstatementevidence.md) or [`DocumentEvidence`](documentevidence.md) or [`StructuredEvidence`](structuredevidence.md) or [`ExternalProposalEvidence`](externalproposalevidence.md) | Yes | Not specified |
| `content_sha256` | `string` | Yes | Not specified |
| `evidence_sha256` | `string` | Yes | Not specified |
| `operation_id` | `string` | Yes | Not specified |
| `author_subject` | `string` | Yes | Not specified |
| `committed_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### item_id

- Minimum length: `1`
- Maximum length: `64`

### version

- Minimum: `1`

### version_id

- Minimum length: `1`
- Maximum length: `64`

### publication

- Allowed values: `"draft"`, `"published"`

### evidence

- Minimum items: `1`
- Maximum items: `500`
- Each item: Discriminator field: `kind`
- Each item: For `"document_passage"`: [`DocumentEvidence`](documentevidence.md)
- Each item: For `"external_proposal"`: [`ExternalProposalEvidence`](externalproposalevidence.md)
- Each item: For `"structured_snapshot"`: [`StructuredEvidence`](structuredevidence.md)
- Each item: For `"user_statement"`: [`UserStatementEvidence`](userstatementevidence.md)

### content_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### evidence_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### operation_id

- Minimum length: `1`
- Maximum length: `64`

### author_subject

- Minimum length: `1`
- Maximum length: `512`

### committed_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "item_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Item Id",
          "type": "string"
        },
        "version": {
          "minimum": 1,
          "title": "Version",
          "type": "integer"
        },
        "version_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Version Id",
          "type": "string"
        },
        "publication": {
          "enum": [
            "draft",
            "published"
          ],
          "title": "Publication",
          "type": "string"
        },
        "serving": {
          "title": "Serving",
          "type": "boolean"
        },
        "content": {
          "$ref": "#/$defs/KnowledgeContent"
        },
        "evidence": {
          "items": {
            "discriminator": {
              "mapping": {
                "document_passage": "#/$defs/DocumentEvidence",
                "external_proposal": "#/$defs/ExternalProposalEvidence",
                "structured_snapshot": "#/$defs/StructuredEvidence",
                "user_statement": "#/$defs/UserStatementEvidence"
              },
              "propertyName": "kind"
            },
            "oneOf": [
              {
                "$ref": "#/$defs/UserStatementEvidence"
              },
              {
                "$ref": "#/$defs/DocumentEvidence"
              },
              {
                "$ref": "#/$defs/StructuredEvidence"
              },
              {
                "$ref": "#/$defs/ExternalProposalEvidence"
              }
            ]
          },
          "maxItems": 500,
          "minItems": 1,
          "title": "Evidence",
          "type": "array"
        },
        "content_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Content Sha256",
          "type": "string"
        },
        "evidence_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Evidence Sha256",
          "type": "string"
        },
        "operation_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Operation Id",
          "type": "string"
        },
        "author_subject": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Author Subject",
          "type": "string"
        },
        "committed_at": {
          "format": "date-time",
          "title": "Committed At",
          "type": "string"
        }
      },
      "required": [
        "item_id",
        "version",
        "version_id",
        "publication",
        "serving",
        "content",
        "evidence",
        "content_sha256",
        "evidence_sha256",
        "operation_id",
        "author_subject",
        "committed_at"
      ],
      "title": "KnowledgeVersionView",
      "type": "object"
    }
    ```
