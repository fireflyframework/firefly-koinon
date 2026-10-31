<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationBranding

[All wire models](index.md)

Model aliases: `OrganizationBranding`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `schema_version` | `integer` | No | `1` |
| `revision` | `integer` | Yes | Not specified |
| `origin` | `string` | Yes | Not specified |
| `branding` | [`BrandingValues`](brandingvalues.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### schema_version

- Exact value: `1`

### revision

- Minimum: `0`
- Maximum: `2147483647`

### origin

- Allowed values: `"deployment"`, `"organization"`


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
        "schema_version": {
          "const": 1,
          "default": 1,
          "title": "Schema Version",
          "type": "integer"
        },
        "revision": {
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Revision",
          "type": "integer"
        },
        "origin": {
          "enum": [
            "deployment",
            "organization"
          ],
          "title": "Origin",
          "type": "string"
        },
        "branding": {
          "$ref": "#/$defs/BrandingValues"
        }
      },
      "required": [
        "tenant_id",
        "revision",
        "origin",
        "branding"
      ],
      "title": "OrganizationBranding",
      "type": "object"
    }
    ```
