<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationChatSettingsInput

[All wire models](index.md)

Model aliases: `OrganizationChatSettingsInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `default_agent_id` | `string` or `null` | Yes | Not specified |
| `expected_revision` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### default_agent_id

- anyOf branch 1 (`string`): Maximum length: `64`

### expected_revision

- Minimum: `0`
- Maximum: `2147483646`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "default_agent_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Default Agent Id"
        },
        "expected_revision": {
          "maximum": 2147483646,
          "minimum": 0,
          "title": "Expected Revision",
          "type": "integer"
        }
      },
      "required": [
        "default_agent_id",
        "expected_revision"
      ],
      "title": "OrganizationChatSettingsInput",
      "type": "object"
    }
    ```
