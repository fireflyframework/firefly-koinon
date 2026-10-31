<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationProfileMappingInput

[All wire models](index.md)

Model aliases: `OrganizationProfileMappingInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `enabled` | `boolean` | Yes | Not specified |
| `fields` | [`OrganizationProfileFields`](organizationprofilefields.md) | Yes | Not specified |
| `profile_sync` | [`CorporateProfileSyncPolicy`](corporateprofilesyncpolicy.md) or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

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
        "expected_revision": {
          "maximum": 2147483646,
          "minimum": 0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "enabled": {
          "title": "Enabled",
          "type": "boolean"
        },
        "fields": {
          "$ref": "#/$defs/OrganizationProfileFields"
        },
        "profile_sync": {
          "anyOf": [
            {
              "$ref": "#/$defs/CorporateProfileSyncPolicy"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "expected_revision",
        "enabled",
        "fields"
      ],
      "title": "OrganizationProfileMappingInput",
      "type": "object"
    }
    ```
