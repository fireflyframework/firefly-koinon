<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeIntent

[All wire models](index.md)

Model aliases: `KnowledgeIntent`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `owner_subject` | `string` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |
| `destination` | [`KnowledgeDestination`](knowledgedestination.md) | Yes | Not specified |
| `target_item_id` | `string` | Yes | Not specified |
| `expected_version` | `integer` or `null` | No | `null` |
| `before` | [`KnowledgeContent`](knowledgecontent.md) or `null` | No | `null` |
| `after` | [`KnowledgeContent`](knowledgecontent.md) | Yes | Not specified |
| `evidence` | Array of [`UserStatementEvidence`](userstatementevidence.md) or [`DocumentEvidence`](documentevidence.md) or [`StructuredEvidence`](structuredevidence.md) or [`ExternalProposalEvidence`](externalproposalevidence.md) | Yes | Not specified |
| `authorization_digest` | `string` | Yes | Not specified |
| `remembered_context_present` | `boolean` | No | `false` |
| `status` | `string` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `receipt` | [`KnowledgeCommitReceipt`](knowledgecommitreceipt.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### revision

- Minimum: `1`

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### owner_subject

- Minimum length: `1`
- Maximum length: `512`

### action

- Allowed values: `"create_draft"`, `"create_published"`, `"update_draft"`, `"update_published"`, `"publish_draft"`

### target_item_id

- Minimum length: `1`
- Maximum length: `64`

### expected_version

- anyOf branch 1 (`integer`): Minimum: `1`

### evidence

- Minimum items: `1`
- Maximum items: `500`
- Each item: Discriminator field: `kind`
- Each item: For `"document_passage"`: [`DocumentEvidence`](documentevidence.md)
- Each item: For `"external_proposal"`: [`ExternalProposalEvidence`](externalproposalevidence.md)
- Each item: For `"structured_snapshot"`: [`StructuredEvidence`](structuredevidence.md)
- Each item: For `"user_statement"`: [`UserStatementEvidence`](userstatementevidence.md)

### authorization_digest

- Pattern: `"^[a-f0-9]{64}$"`

### status

- Allowed values: `"preview"`, `"committing"`, `"committed"`, `"cancelled"`, `"stale"`, `"unresolved"`

### created_at

- Format: `"date-time"`

### expires_at

- Format: `"date-time"`


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
        "revision": {
          "minimum": 1,
          "title": "Revision",
          "type": "integer"
        },
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "owner_subject": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Owner Subject",
          "type": "string"
        },
        "action": {
          "enum": [
            "create_draft",
            "create_published",
            "update_draft",
            "update_published",
            "publish_draft"
          ],
          "title": "Action",
          "type": "string"
        },
        "destination": {
          "$ref": "#/$defs/KnowledgeDestination"
        },
        "target_item_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Target Item Id",
          "type": "string"
        },
        "expected_version": {
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
          "title": "Expected Version"
        },
        "before": {
          "anyOf": [
            {
              "$ref": "#/$defs/KnowledgeContent"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "after": {
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
        "authorization_digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Authorization Digest",
          "type": "string"
        },
        "remembered_context_present": {
          "default": false,
          "title": "Remembered Context Present",
          "type": "boolean"
        },
        "status": {
          "enum": [
            "preview",
            "committing",
            "committed",
            "cancelled",
            "stale",
            "unresolved"
          ],
          "title": "Status",
          "type": "string"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        },
        "receipt": {
          "anyOf": [
            {
              "$ref": "#/$defs/KnowledgeCommitReceipt"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "id",
        "revision",
        "tenant_id",
        "owner_subject",
        "action",
        "destination",
        "target_item_id",
        "after",
        "evidence",
        "authorization_digest",
        "status",
        "created_at",
        "expires_at"
      ],
      "title": "KnowledgeIntent",
      "type": "object"
    }
    ```
