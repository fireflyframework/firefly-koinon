<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationProfileFields

[All wire models](index.md)

Model aliases: `OrganizationProfileFields`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `job_title` | `string` or `null` | No | `null` |
| `unit_external_key` | `string` or `null` | No | `null` |
| `manager_external_subject` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### job_title

- anyOf branch 1 (`string`): Pattern: `"^[A-Za-z][A-Za-z0-9_]{0,79}$"`

### unit_external_key

- anyOf branch 1 (`string`): Pattern: `"^[A-Za-z][A-Za-z0-9_]{0,79}$"`

### manager_external_subject

- anyOf branch 1 (`string`): Pattern: `"^[A-Za-z][A-Za-z0-9_]{0,79}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
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
        "unit_external_key": {
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
          "title": "Unit External Key"
        },
        "manager_external_subject": {
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
          "title": "Manager External Subject"
        }
      },
      "title": "OrganizationProfileFields",
      "type": "object"
    }
    ```
