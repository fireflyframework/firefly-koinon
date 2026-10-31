<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CorporateProfileSyncPolicy

[All wire models](index.md)

Model aliases: `CorporateProfileSyncPolicy`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `interval_seconds` | `integer` | No | `900` |
| `allow_personal_overrides` | `boolean` | No | `true` |
| `name_source` | `string` | No | `"directory"` |
| `avatar_source` | `string` | No | `"directory"` |
| `job_title_source` | `string` | No | `"directory"` |
| `unit_source` | `string` | No | `"directory"` |
| `manager_source` | `string` | No | `"verified_claims"` |
| `google_department` | `string` | No | `"department"` |
| `keycloak_attributes` | [`KeycloakProfileAttributes`](keycloakprofileattributes.md) | No | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### interval_seconds

- Minimum: `300`
- Maximum: `86400`

### name_source

- Allowed values: `"directory"`, `"personal"`

### avatar_source

- Allowed values: `"directory"`, `"personal"`

### job_title_source

- Allowed values: `"directory"`, `"verified_claims"`, `"local"`

### unit_source

- Allowed values: `"directory"`, `"verified_claims"`, `"local"`

### manager_source

- Allowed values: `"directory"`, `"verified_claims"`, `"local"`

### google_department

- Allowed values: `"department"`, `"org_unit_path"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "interval_seconds": {
          "default": 900,
          "maximum": 86400,
          "minimum": 300,
          "title": "Interval Seconds",
          "type": "integer"
        },
        "allow_personal_overrides": {
          "default": true,
          "title": "Allow Personal Overrides",
          "type": "boolean"
        },
        "name_source": {
          "default": "directory",
          "enum": [
            "directory",
            "personal"
          ],
          "title": "Name Source",
          "type": "string"
        },
        "avatar_source": {
          "default": "directory",
          "enum": [
            "directory",
            "personal"
          ],
          "title": "Avatar Source",
          "type": "string"
        },
        "job_title_source": {
          "default": "directory",
          "enum": [
            "directory",
            "verified_claims",
            "local"
          ],
          "title": "Job Title Source",
          "type": "string"
        },
        "unit_source": {
          "default": "directory",
          "enum": [
            "directory",
            "verified_claims",
            "local"
          ],
          "title": "Unit Source",
          "type": "string"
        },
        "manager_source": {
          "default": "verified_claims",
          "enum": [
            "directory",
            "verified_claims",
            "local"
          ],
          "title": "Manager Source",
          "type": "string"
        },
        "google_department": {
          "default": "department",
          "enum": [
            "department",
            "org_unit_path"
          ],
          "title": "Google Department",
          "type": "string"
        },
        "keycloak_attributes": {
          "$ref": "#/$defs/KeycloakProfileAttributes"
        }
      },
      "title": "CorporateProfileSyncPolicy",
      "type": "object"
    }
    ```
