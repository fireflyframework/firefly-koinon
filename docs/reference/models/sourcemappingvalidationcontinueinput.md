<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceMappingValidationContinueInput

[All wire models](index.md)

Model aliases: `SourceMappingValidationContinueInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `continuation_token` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`

### continuation_token

- Minimum length: `1`
- Maximum length: `4096`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        },
        "continuation_token": {
          "maxLength": 4096,
          "minLength": 1,
          "title": "Continuation Token",
          "type": "string"
        }
      },
      "required": [
        "expected_revision",
        "continuation_token"
      ],
      "title": "SourceMappingValidationContinueInput",
      "type": "object"
    }
    ```
