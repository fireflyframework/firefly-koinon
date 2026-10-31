<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IdentityActivation

[All wire models](index.md)

Model aliases: `IdentityActivation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `validation_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`

### validation_id

- Minimum length: `1`
- Maximum length: `64`


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
        "validation_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Validation Id",
          "type": "string"
        }
      },
      "required": [
        "expected_revision",
        "validation_id"
      ],
      "title": "IdentityActivation",
      "type": "object"
    }
    ```
