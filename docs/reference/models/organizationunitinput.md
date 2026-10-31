<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationUnitInput

[All wire models](index.md)

Model aliases: `OrganizationUnitInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Not specified |
| `kind` | `string` | No | `"department"` |
| `parent_id` | `string` or `null` | No | `null` |
| `provider_id` | `string` or `null` | No | `null` |
| `external_key` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### name

- Minimum length: `1`
- Maximum length: `160`

### kind

- Allowed values: `"division"`, `"department"`, `"team"`

### parent_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### provider_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### external_key

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `256`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 160,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "kind": {
          "default": "department",
          "enum": [
            "division",
            "department",
            "team"
          ],
          "title": "Kind",
          "type": "string"
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
        },
        "provider_id": {
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
          "title": "Provider Id"
        },
        "external_key": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "External Key"
        }
      },
      "required": [
        "name"
      ],
      "title": "OrganizationUnitInput",
      "type": "object"
    }
    ```
