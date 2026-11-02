<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# WelcomeRecoveryInput

[All wire models](index.md)

Model aliases: `WelcomeRecoveryInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_generation` | `integer` | Yes | Not specified |
| `contact_id` | `string` | Yes | Not specified |
| `expected_contact_revision` | `integer` | Yes | Not specified |
| `reason` | `string` | Yes | Not specified |
| `acknowledge_possible_duplicate` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_generation

- Minimum: `0`

### contact_id

- Minimum length: `1`
- Maximum length: `64`

### expected_contact_revision

- Minimum: `1`

### reason

- Exact value: `"recipient_reported_not_received"`

### acknowledge_possible_duplicate

- Exact value: `true`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_generation": {
          "minimum": 0,
          "title": "Expected Generation",
          "type": "integer"
        },
        "contact_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Contact Id",
          "type": "string"
        },
        "expected_contact_revision": {
          "minimum": 1,
          "title": "Expected Contact Revision",
          "type": "integer"
        },
        "reason": {
          "const": "recipient_reported_not_received",
          "title": "Reason",
          "type": "string"
        },
        "acknowledge_possible_duplicate": {
          "const": true,
          "title": "Acknowledge Possible Duplicate",
          "type": "boolean"
        }
      },
      "required": [
        "expected_generation",
        "contact_id",
        "expected_contact_revision",
        "reason",
        "acknowledge_possible_duplicate"
      ],
      "title": "WelcomeRecoveryInput",
      "type": "object"
    }
    ```
