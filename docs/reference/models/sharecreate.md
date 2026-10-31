<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ShareCreate

[All wire models](index.md)

Model aliases: `ShareCreate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `review_id` | `string` | Yes | Not specified |
| `expected_revision` | `string` | Yes | Not specified |
| `expires_in_hours` | `integer` | No | `24` |
| `recipient_policy` | `string` | No | `"organization_current_acl"` |
| `include_remembered_context` | `boolean` | No | `false` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### review_id

- Minimum length: `1`
- Maximum length: `64`

### expected_revision

- Pattern: `"^[a-f0-9]{64}$"`

### expires_in_hours

- Minimum: `1`
- Maximum: `168`

### recipient_policy

- Exact value: `"organization_current_acl"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "review_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Review Id",
          "type": "string"
        },
        "expected_revision": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Expected Revision",
          "type": "string"
        },
        "expires_in_hours": {
          "default": 24,
          "maximum": 168,
          "minimum": 1,
          "title": "Expires In Hours",
          "type": "integer"
        },
        "recipient_policy": {
          "const": "organization_current_acl",
          "default": "organization_current_acl",
          "title": "Recipient Policy",
          "type": "string"
        },
        "include_remembered_context": {
          "default": false,
          "title": "Include Remembered Context",
          "type": "boolean"
        }
      },
      "required": [
        "review_id",
        "expected_revision"
      ],
      "title": "ShareCreate",
      "type": "object"
    }
    ```
