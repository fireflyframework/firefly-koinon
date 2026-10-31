<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationPresentationInput

[All wire models](index.md)

Model aliases: `OrganizationPresentationInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `name_mode` | `string` | No | `null` |
| `avatar_mode` | `string` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `0`
- Maximum: `2147483646`

### name_mode

- Allowed values: `"organization"`, `"personal"`

### avatar_mode

- Allowed values: `"organization"`, `"personal"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "maximum": 2147483646,
          "minimum": 0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "name_mode": {
          "default": null,
          "enum": [
            "organization",
            "personal"
          ],
          "title": "Name Mode",
          "type": "string"
        },
        "avatar_mode": {
          "default": null,
          "enum": [
            "organization",
            "personal"
          ],
          "title": "Avatar Mode",
          "type": "string"
        }
      },
      "required": [
        "expected_revision"
      ],
      "title": "OrganizationPresentationInput",
      "type": "object"
    }
    ```
