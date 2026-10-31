<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# UserStatementEvidence

[All wire models](index.md)

Model aliases: `UserStatementEvidence`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | No | `"user_statement"` |
| `text` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `author_subject` | `string` | Yes | Not specified |
| `recorded_at` | `string` | Yes | Not specified |
| `authority` | `string` | No | `"user_authored"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Exact value: `"user_statement"`

### text

- Minimum length: `1`
- Maximum length: `262144`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`

### author_subject

- Minimum length: `1`
- Maximum length: `512`

### recorded_at

- Format: `"date-time"`

### authority

- Exact value: `"user_authored"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "kind": {
          "const": "user_statement",
          "default": "user_statement",
          "title": "Kind",
          "type": "string"
        },
        "text": {
          "maxLength": 262144,
          "minLength": 1,
          "title": "Text",
          "type": "string"
        },
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
          "type": "string"
        },
        "author_subject": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Author Subject",
          "type": "string"
        },
        "recorded_at": {
          "format": "date-time",
          "title": "Recorded At",
          "type": "string"
        },
        "authority": {
          "const": "user_authored",
          "default": "user_authored",
          "title": "Authority",
          "type": "string"
        }
      },
      "required": [
        "text",
        "sha256",
        "author_subject",
        "recorded_at"
      ],
      "title": "UserStatementEvidence",
      "type": "object"
    }
    ```
