<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationProfileMapping

[All wire models](index.md)

Model aliases: `OrganizationProfileMapping`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `provider_id` | `string` | Yes | Not specified |
| `revision` | `integer` | No | `0` |
| `enabled` | `boolean` | No | `false` |
| `fields` | [`OrganizationProfileFields`](organizationprofilefields.md) | No | Not specified |
| `source` | `string` | No | `"verified_claims"` |
| `profile_sync` | [`CorporateProfileSyncPolicy`](corporateprofilesyncpolicy.md) or `null` | No | `null` |
| `profile_capabilities` | Array of [`CorporateProfileFieldCapability`](corporateprofilefieldcapability.md) | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### revision

- Minimum: `0`
- Maximum: `2147483647`

### source

- Exact value: `"verified_claims"`

### profile_capabilities

- Maximum items: `5`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "provider_id": {
          "title": "Provider Id",
          "type": "string"
        },
        "revision": {
          "default": 0,
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Revision",
          "type": "integer"
        },
        "enabled": {
          "default": false,
          "title": "Enabled",
          "type": "boolean"
        },
        "fields": {
          "$ref": "#/$defs/OrganizationProfileFields"
        },
        "source": {
          "const": "verified_claims",
          "default": "verified_claims",
          "title": "Source",
          "type": "string"
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
        },
        "profile_capabilities": {
          "items": {
            "$ref": "#/$defs/CorporateProfileFieldCapability"
          },
          "maxItems": 5,
          "title": "Profile Capabilities",
          "type": "array"
        }
      },
      "required": [
        "tenant_id",
        "provider_id"
      ],
      "title": "OrganizationProfileMapping",
      "type": "object"
    }
    ```
