<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationPersonCreate

[All wire models](index.md)

Model aliases: `OrganizationPersonCreate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `profile_id` | `string` or `null` | No | `null` |
| `subject` | `string` or `null` | No | `null` |
| `job_title` | `string` or `null` | No | `null` |
| `unit_id` | `string` or `null` | No | `null` |
| `manager_id` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### profile_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### subject

- anyOf branch 1 (`string`): Minimum length: `3`
- anyOf branch 1 (`string`): Maximum length: `512`

### job_title

- anyOf branch 1 (`string`): Maximum length: `160`

### unit_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### manager_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "profile_id": {
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
          "title": "Profile Id"
        },
        "subject": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 3,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Subject"
        },
        "job_title": {
          "anyOf": [
            {
              "maxLength": 160,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Job Title"
        },
        "unit_id": {
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
          "title": "Unit Id"
        },
        "manager_id": {
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
          "title": "Manager Id"
        }
      },
      "title": "OrganizationPersonCreate",
      "type": "object"
    }
    ```
