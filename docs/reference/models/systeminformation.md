<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SystemInformation

[All wire models](index.md)

Model aliases: `SystemInformation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tenant_id` | `string` | Yes | Not specified |
| `checked_at` | `string` | Yes | Not specified |
| `product` | `string` | No | `"koinon"` |
| `components` | Array of [`SystemComponentVersion`](systemcomponentversion.md) | Yes | Not specified |
| `serving_role` | `string` | Yes | Not specified |
| `capabilities` | [`SystemCapabilities`](systemcapabilities.md) | Yes | Not specified |
| `limits` | Array of [`SystemLimit`](systemlimit.md) | Yes | Not specified |
| `build_revision` | `string` or `null` | No | `null` |
| `license_expression` | `string` | No | `"Apache-2.0"` |
| `copyright` | `string` | No | `"Copyright 2026 Firefly Software Foundation"` |
| `artifacts` | Array of [`SystemArtifact`](systemartifact.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### checked_at

- Format: `"date-time"`

### product

- Exact value: `"koinon"`

### components

- Maximum items: `6`

### serving_role

- Allowed values: `"api"`, `"worker"`, `"unknown"`

### limits

- Maximum items: `10`

### build_revision

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{40}$"`

### license_expression

- Exact value: `"Apache-2.0"`

### copyright

- Exact value: `"Copyright 2026 Firefly Software Foundation"`

### artifacts

- Maximum items: `18`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "checked_at": {
          "format": "date-time",
          "title": "Checked At",
          "type": "string"
        },
        "product": {
          "const": "koinon",
          "default": "koinon",
          "title": "Product",
          "type": "string"
        },
        "components": {
          "items": {
            "$ref": "#/$defs/SystemComponentVersion"
          },
          "maxItems": 6,
          "title": "Components",
          "type": "array"
        },
        "serving_role": {
          "enum": [
            "api",
            "worker",
            "unknown"
          ],
          "title": "Serving Role",
          "type": "string"
        },
        "capabilities": {
          "$ref": "#/$defs/SystemCapabilities"
        },
        "limits": {
          "items": {
            "$ref": "#/$defs/SystemLimit"
          },
          "maxItems": 10,
          "title": "Limits",
          "type": "array"
        },
        "build_revision": {
          "anyOf": [
            {
              "pattern": "^[a-f0-9]{40}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Build Revision"
        },
        "license_expression": {
          "const": "Apache-2.0",
          "default": "Apache-2.0",
          "title": "License Expression",
          "type": "string"
        },
        "copyright": {
          "const": "Copyright 2026 Firefly Software Foundation",
          "default": "Copyright 2026 Firefly Software Foundation",
          "title": "Copyright",
          "type": "string"
        },
        "artifacts": {
          "items": {
            "$ref": "#/$defs/SystemArtifact"
          },
          "maxItems": 18,
          "title": "Artifacts",
          "type": "array"
        }
      },
      "required": [
        "tenant_id",
        "checked_at",
        "components",
        "serving_role",
        "capabilities",
        "limits",
        "artifacts"
      ],
      "title": "SystemInformation",
      "type": "object"
    }
    ```
