<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AnswerPolicy

[All wire models](index.md)

Model aliases: `AnswerPolicy`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `outcome` | `string` | Yes | Not specified |
| `code` | `string` or `null` | No | `null` |
| `reason` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### outcome

- Allowed values: `"grounded"`, `"refused"`, `"review_required"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "outcome": {
          "enum": [
            "grounded",
            "refused",
            "review_required"
          ],
          "title": "Outcome",
          "type": "string"
        },
        "code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Code"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason"
        }
      },
      "required": [
        "outcome"
      ],
      "title": "AnswerPolicy",
      "type": "object"
    }
    ```
