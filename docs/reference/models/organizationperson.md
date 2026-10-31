<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationPerson

[All wire models](index.md)

Model aliases: `OrganizationPerson`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` or `null` | No | `null` |
| `profile_id` | `string` or `null` | No | `null` |
| `display_name` | `string` | Yes | Not specified |
| `avatar_url` | `string` or `null` | No | `null` |
| `avatar_version` | `string` or `null` | No | `null` |
| `job_title` | `string` or `null` | No | `null` |
| `unit` | [`OrganizationUnitSummary`](organizationunitsummary.md) or `null` | No | `null` |
| `department` | [`OrganizationUnitSummary`](organizationunitsummary.md) or `null` | No | `null` |
| `manager` | [`OrganizationPersonReference`](organizationpersonreference.md) or `null` | No | `null` |
| `manager_unavailable` | `boolean` | No | `false` |
| `revision` | `integer` | No | `0` |
| `source` | `string` | No | `"unassigned"` |
| `provider_id` | `string` or `null` | No | `null` |
| `provider_name` | `string` or `null` | No | `null` |
| `managed_fields` | Array of `string` | No | Not specified |
| `observed_at` | `string` or `null` | No | `null` |
| `updated_at` | `string` or `null` | No | `null` |
| `observation_status` | `string` | No | `"not_observed"` |
| `presentation` | [`CorporatePresentationSummary`](corporatepresentationsummary.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### revision

- Minimum: `0`
- Maximum: `2147483647`

### source

- Allowed values: `"unassigned"`, `"manual"`, `"provider"`

### managed_fields

- Each item: Allowed values: `"job_title"`, `"unit_id"`, `"manager_id"`

### observed_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### updated_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### observation_status

- Allowed values: `"not_observed"`, `"current"`, `"unavailable"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "profile_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Profile Id"
        },
        "display_name": {
          "title": "Display Name",
          "type": "string"
        },
        "avatar_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Avatar Url"
        },
        "avatar_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Avatar Version"
        },
        "job_title": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Job Title"
        },
        "unit": {
          "anyOf": [
            {
              "$ref": "#/$defs/OrganizationUnitSummary"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "department": {
          "anyOf": [
            {
              "$ref": "#/$defs/OrganizationUnitSummary"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "manager": {
          "anyOf": [
            {
              "$ref": "#/$defs/OrganizationPersonReference"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "manager_unavailable": {
          "default": false,
          "title": "Manager Unavailable",
          "type": "boolean"
        },
        "revision": {
          "default": 0,
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Revision",
          "type": "integer"
        },
        "source": {
          "default": "unassigned",
          "enum": [
            "unassigned",
            "manual",
            "provider"
          ],
          "title": "Source",
          "type": "string"
        },
        "provider_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Provider Id"
        },
        "provider_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Provider Name"
        },
        "managed_fields": {
          "items": {
            "enum": [
              "job_title",
              "unit_id",
              "manager_id"
            ],
            "type": "string"
          },
          "title": "Managed Fields",
          "type": "array"
        },
        "observed_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed At"
        },
        "updated_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Updated At"
        },
        "observation_status": {
          "default": "not_observed",
          "enum": [
            "not_observed",
            "current",
            "unavailable"
          ],
          "title": "Observation Status",
          "type": "string"
        },
        "presentation": {
          "anyOf": [
            {
              "$ref": "#/$defs/CorporatePresentationSummary"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "display_name"
      ],
      "title": "OrganizationPerson",
      "type": "object"
    }
    ```
