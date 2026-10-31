<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KeycloakProfileAttributes

[All wire models](index.md)

Model aliases: `KeycloakProfileAttributes`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `display_name` | `string` or `null` | No | `null` |
| `job_title` | `string` or `null` | No | `null` |
| `department` | `string` or `null` | No | `null` |
| `manager` | `string` or `null` | No | `null` |
| `picture` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### display_name

- anyOf branch 1 (`string`): Pattern: `"^[A-Za-z][A-Za-z0-9_]{0,79}$"`

### job_title

- anyOf branch 1 (`string`): Pattern: `"^[A-Za-z][A-Za-z0-9_]{0,79}$"`

### department

- anyOf branch 1 (`string`): Pattern: `"^[A-Za-z][A-Za-z0-9_]{0,79}$"`

### manager

- anyOf branch 1 (`string`): Pattern: `"^[A-Za-z][A-Za-z0-9_]{0,79}$"`

### picture

- anyOf branch 1 (`string`): Pattern: `"^[A-Za-z][A-Za-z0-9_]{0,79}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "display_name": {
          "anyOf": [
            {
              "pattern": "^[A-Za-z][A-Za-z0-9_]{0,79}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Display Name"
        },
        "job_title": {
          "anyOf": [
            {
              "pattern": "^[A-Za-z][A-Za-z0-9_]{0,79}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Job Title"
        },
        "department": {
          "anyOf": [
            {
              "pattern": "^[A-Za-z][A-Za-z0-9_]{0,79}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Department"
        },
        "manager": {
          "anyOf": [
            {
              "pattern": "^[A-Za-z][A-Za-z0-9_]{0,79}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Manager"
        },
        "picture": {
          "anyOf": [
            {
              "pattern": "^[A-Za-z][A-Za-z0-9_]{0,79}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Picture"
        }
      },
      "title": "KeycloakProfileAttributes",
      "type": "object"
    }
    ```
