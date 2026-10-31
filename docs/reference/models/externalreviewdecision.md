<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalReviewDecision

[All wire models](index.md)

Model aliases: `ExternalReviewDecision`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `authorization_digest` | `string` | Yes | Not specified |
| `nonce` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`

### authorization_digest

- Pattern: `"^[a-f0-9]{64}$"`

### nonce

- Minimum length: `43`
- Maximum length: `43`


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
        "authorization_digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Authorization Digest",
          "type": "string"
        },
        "nonce": {
          "maxLength": 43,
          "minLength": 43,
          "title": "Nonce",
          "type": "string"
        }
      },
      "required": [
        "expected_revision",
        "authorization_digest",
        "nonce"
      ],
      "title": "ExternalReviewDecision",
      "type": "object"
    }
    ```
