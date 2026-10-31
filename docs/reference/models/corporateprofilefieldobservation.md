<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CorporateProfileFieldObservation

[All wire models](index.md)

Model aliases: `CorporateProfileFieldObservation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `field` | `string` | Yes | Not specified |
| `source` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `observed_at` | `string` or `null` | No | `null` |
| `code` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### field

- Allowed values: `"display_name"`, `"avatar"`, `"job_title"`, `"department"`, `"manager"`

### source

- Allowed values: `"directory"`, `"verified_claims"`, `"local"`, `"personal"`

### status

- Allowed values: `"not_observed"`, `"current"`, `"empty"`, `"unavailable"`, `"unsupported"`, `"stale"`

### observed_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### code

- anyOf branch 1 (`string`): Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "field": {
          "enum": [
            "display_name",
            "avatar",
            "job_title",
            "department",
            "manager"
          ],
          "title": "Field",
          "type": "string"
        },
        "source": {
          "enum": [
            "directory",
            "verified_claims",
            "local",
            "personal"
          ],
          "title": "Source",
          "type": "string"
        },
        "status": {
          "enum": [
            "not_observed",
            "current",
            "empty",
            "unavailable",
            "unsupported",
            "stale"
          ],
          "title": "Status",
          "type": "string"
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
        "code": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Code"
        }
      },
      "required": [
        "field",
        "source",
        "status"
      ],
      "title": "CorporateProfileFieldObservation",
      "type": "object"
    }
    ```
