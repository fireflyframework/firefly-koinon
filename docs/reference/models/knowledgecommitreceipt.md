<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeCommitReceipt

[All wire models](index.md)

Model aliases: `KnowledgeCommitReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `operation_id` | `string` | Yes | Not specified |
| `intent_id` | `string` | Yes | Not specified |
| `intent_revision` | `integer` | Yes | Not specified |
| `authorization_digest` | `string` | Yes | Not specified |
| `item_id` | `string` | Yes | Not specified |
| `native_item_id` | `string` | Yes | Not specified |
| `native_version_id` | `string` | Yes | Not specified |
| `version` | `integer` | Yes | Not specified |
| `serving_version` | `integer` or `null` | No | `null` |
| `action` | `string` | Yes | Not specified |
| `content_sha256` | `string` | Yes | Not specified |
| `evidence_sha256` | `string` | Yes | Not specified |
| `committed_at` | `string` | Yes | Not specified |
| `retrieval_state` | `string` | Yes | Not specified |
| `reason` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### operation_id

- Minimum length: `1`
- Maximum length: `64`

### intent_id

- Minimum length: `1`
- Maximum length: `64`

### intent_revision

- Minimum: `1`

### authorization_digest

- Pattern: `"^[a-f0-9]{64}$"`

### item_id

- Minimum length: `1`
- Maximum length: `64`

### native_item_id

- Minimum length: `1`
- Maximum length: `64`

### native_version_id

- Minimum length: `1`
- Maximum length: `64`

### version

- Minimum: `1`

### serving_version

- anyOf branch 1 (`integer`): Minimum: `1`

### action

- Allowed values: `"create_draft"`, `"create_published"`, `"update_draft"`, `"update_published"`, `"publish_draft"`

### content_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### evidence_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### committed_at

- Format: `"date-time"`

### retrieval_state

- Allowed values: `"not_published"`, `"lexical_ready"`, `"indexing"`, `"ready"`, `"unavailable"`

### reason

- anyOf branch 1 (`string`): Maximum length: `512`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "operation_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Operation Id",
          "type": "string"
        },
        "intent_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Intent Id",
          "type": "string"
        },
        "intent_revision": {
          "minimum": 1,
          "title": "Intent Revision",
          "type": "integer"
        },
        "authorization_digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Authorization Digest",
          "type": "string"
        },
        "item_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Item Id",
          "type": "string"
        },
        "native_item_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Native Item Id",
          "type": "string"
        },
        "native_version_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Native Version Id",
          "type": "string"
        },
        "version": {
          "minimum": 1,
          "title": "Version",
          "type": "integer"
        },
        "serving_version": {
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
          "title": "Serving Version"
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
        "committed_at": {
          "format": "date-time",
          "title": "Committed At",
          "type": "string"
        },
        "retrieval_state": {
          "enum": [
            "not_published",
            "lexical_ready",
            "indexing",
            "ready",
            "unavailable"
          ],
          "title": "Retrieval State",
          "type": "string"
        },
        "reason": {
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
          "title": "Reason"
        }
      },
      "required": [
        "operation_id",
        "intent_id",
        "intent_revision",
        "authorization_digest",
        "item_id",
        "native_item_id",
        "native_version_id",
        "version",
        "action",
        "content_sha256",
        "evidence_sha256",
        "committed_at",
        "retrieval_state"
      ],
      "title": "KnowledgeCommitReceipt",
      "type": "object"
    }
    ```
