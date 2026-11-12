<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourcePolicyOperationOutput

[All wire models](index.md)

Model aliases: `SourcePolicyOperationOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `schema` | `string` | No | `"koinon.source-policy-operation.v1"` |
| `receipt_id` | `string` | Yes | Not specified |
| `operation_id` | `string` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |
| `mapping_id` | `string` | Yes | Not specified |
| `policy_id` | `string` | Yes | Not specified |
| `expected_policy_revision` | `integer` or `null` | Yes | Not specified |
| `result_policy_revision` | `integer` | Yes | Not specified |
| `review_digest` | `string` | Yes | Not specified |
| `review_expires_at` | `string` | Yes | Not specified |
| `disposition` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### schema

- Exact value: `"koinon.source-policy-operation.v1"`

### receipt_id

- Minimum length: `1`
- Maximum length: `64`

### action

- Allowed values: `"review"`, `"apply"`

### mapping_id

- Minimum length: `1`
- Maximum length: `64`

### policy_id

- Minimum length: `1`
- Maximum length: `64`

### review_digest

- Pattern: `"^[a-f0-9]{64}$"`

### review_expires_at

- Format: `"date-time"`

### disposition

- Allowed values: `"reviewed"`, `"accepted"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "schema": {
          "const": "koinon.source-policy-operation.v1",
          "default": "koinon.source-policy-operation.v1",
          "title": "Schema",
          "type": "string"
        },
        "receipt_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Receipt Id",
          "type": "string"
        },
        "operation_id": {
          "title": "Operation Id",
          "type": "string"
        },
        "action": {
          "enum": [
            "review",
            "apply"
          ],
          "title": "Action",
          "type": "string"
        },
        "mapping_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Mapping Id",
          "type": "string"
        },
        "policy_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Policy Id",
          "type": "string"
        },
        "expected_policy_revision": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Expected Policy Revision"
        },
        "result_policy_revision": {
          "title": "Result Policy Revision",
          "type": "integer"
        },
        "review_digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Review Digest",
          "type": "string"
        },
        "review_expires_at": {
          "format": "date-time",
          "title": "Review Expires At",
          "type": "string"
        },
        "disposition": {
          "enum": [
            "reviewed",
            "accepted"
          ],
          "title": "Disposition",
          "type": "string"
        }
      },
      "required": [
        "receipt_id",
        "operation_id",
        "action",
        "mapping_id",
        "policy_id",
        "expected_policy_revision",
        "result_policy_revision",
        "review_digest",
        "review_expires_at",
        "disposition"
      ],
      "title": "SourcePolicyOperationOutput",
      "type": "object"
    }
    ```
