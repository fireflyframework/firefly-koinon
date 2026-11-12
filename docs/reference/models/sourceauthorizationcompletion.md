<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceAuthorizationCompletion

[All wire models](index.md)

Model aliases: `SourceAuthorizationCompletion`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `challenge_id` | `string` | Yes | Not specified |
| `state` | `string` | Yes | Not specified |
| `code` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### challenge_id

- Minimum length: `1`
- Maximum length: `64`

### state

- Minimum length: `1`
- Maximum length: `4096`
- Format: `"password"`
- Write only: `true`

### code

- Minimum length: `1`
- Maximum length: `16384`
- Format: `"password"`
- Write only: `true`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "challenge_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Challenge Id",
          "type": "string"
        },
        "state": {
          "format": "password",
          "maxLength": 4096,
          "minLength": 1,
          "title": "State",
          "type": "string",
          "writeOnly": true
        },
        "code": {
          "format": "password",
          "maxLength": 16384,
          "minLength": 1,
          "title": "Code",
          "type": "string",
          "writeOnly": true
        }
      },
      "required": [
        "challenge_id",
        "state",
        "code"
      ],
      "title": "SourceAuthorizationCompletion",
      "type": "object"
    }
    ```
