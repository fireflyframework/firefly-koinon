<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationUnitPatch

[All wire models](index.md)

Model aliases: `OrganizationUnitPatch`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `name` | `string` or `null` | No | `null` |
| `kind` | `string` or `null` | No | `null` |
| `parent_id` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`
- Maximum: `2147483646`

### name

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `160`

### kind

- anyOf branch 1 (`string`): Allowed values: `"division"`, `"department"`, `"team"`

### parent_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "maximum": 2147483646,
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        },
        "name": {
          "anyOf": [
            {
              "maxLength": 160,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Name"
        },
        "kind": {
          "anyOf": [
            {
              "enum": [
                "division",
                "department",
                "team"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Kind"
        },
        "parent_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Id"
        }
      },
      "required": [
        "expected_revision"
      ],
      "title": "OrganizationUnitPatch",
      "type": "object"
    }
    ```
