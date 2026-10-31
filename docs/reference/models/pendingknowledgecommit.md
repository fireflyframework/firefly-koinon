<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# PendingKnowledgeCommit

[All wire models](index.md)

Model aliases: `PendingKnowledgeCommit`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `status` | `string` | No | `"pending"` |
| `operation_id` | `string` | Yes | Not specified |
| `intent_id` | `string` | Yes | Not specified |
| `reason` | `string` | No | `"commit_outcome_unresolved"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Exact value: `"pending"`

### operation_id

- Minimum length: `1`
- Maximum length: `64`

### intent_id

- Minimum length: `1`
- Maximum length: `64`

### reason

- Exact value: `"commit_outcome_unresolved"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "status": {
          "const": "pending",
          "default": "pending",
          "title": "Status",
          "type": "string"
        },
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
        "reason": {
          "const": "commit_outcome_unresolved",
          "default": "commit_outcome_unresolved",
          "title": "Reason",
          "type": "string"
        }
      },
      "required": [
        "operation_id",
        "intent_id"
      ],
      "title": "PendingKnowledgeCommit",
      "type": "object"
    }
    ```
