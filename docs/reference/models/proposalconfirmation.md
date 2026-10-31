<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProposalConfirmation

[All wire models](index.md)

Model aliases: `ProposalConfirmation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `confirm` | `boolean` | Yes | Not specified |
| `expected_revision` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### confirm

- Exact value: `true`

### expected_revision

- Minimum: `1`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "confirm": {
          "const": true,
          "title": "Confirm",
          "type": "boolean"
        },
        "expected_revision": {
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        }
      },
      "required": [
        "confirm",
        "expected_revision"
      ],
      "title": "ProposalConfirmation",
      "type": "object"
    }
    ```
