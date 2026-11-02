<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AnswerSelectionValidation

[All wire models](index.md)

Model aliases: `AnswerSelectionValidation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `repairs` | `integer` | Yes | Not specified |
| `errors` | Array of `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "repairs": {
          "title": "Repairs",
          "type": "integer"
        },
        "errors": {
          "items": {
            "type": "string"
          },
          "title": "Errors",
          "type": "array"
        }
      },
      "required": [
        "repairs",
        "errors"
      ],
      "title": "AnswerSelectionValidation",
      "type": "object"
    }
    ```
