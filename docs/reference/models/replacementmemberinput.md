<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ReplacementMemberInput

[All wire models](index.md)

Model aliases: `ReplacementMemberInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `new_locator` | `string` | Yes | Not specified |
| `previous_table_id` | `string` or `null` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### new_locator

- Minimum length: `1`
- Maximum length: `2048`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "new_locator": {
          "maxLength": 2048,
          "minLength": 1,
          "title": "New Locator",
          "type": "string"
        },
        "previous_table_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Previous Table Id"
        }
      },
      "required": [
        "new_locator",
        "previous_table_id"
      ],
      "title": "ReplacementMemberInput",
      "type": "object"
    }
    ```
