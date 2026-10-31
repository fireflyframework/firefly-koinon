<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configuration

[All wire models](index.md)

Model aliases: `Configuration`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `framework_providers` | Array of [`ProviderSupport`](providersupport.md) | No | Not specified |
| `model_options_schema` | Map of string keys to [`JsonValue`](jsonvalue.md) | No | Not specified |
| `deployment` | [`DeploymentConfiguration`](deploymentconfiguration.md) or `null` | No | `null` |
| `providers` | Array of [`ModelProvider`](modelprovider.md) | Yes | Not specified |
| `provider_types` | Array of [`ProviderType`](providertype.md) | Yes | Not specified |
| `connections` | Array of [`ModelConnection`](modelconnection.md) | Yes | Not specified |
| `checks` | Array of [`SetupCheck`](setupcheck.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### model_options_schema

- Additional properties: [`JsonValue`](jsonvalue.md)


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "framework_providers": {
          "items": {
            "$ref": "#/$defs/ProviderSupport"
          },
          "title": "Framework Providers",
          "type": "array"
        },
        "model_options_schema": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Model Options Schema",
          "type": "object"
        },
        "deployment": {
          "anyOf": [
            {
              "$ref": "#/$defs/DeploymentConfiguration"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "providers": {
          "items": {
            "$ref": "#/$defs/ModelProvider"
          },
          "title": "Providers",
          "type": "array"
        },
        "provider_types": {
          "items": {
            "$ref": "#/$defs/ProviderType"
          },
          "title": "Provider Types",
          "type": "array"
        },
        "connections": {
          "items": {
            "$ref": "#/$defs/ModelConnection"
          },
          "title": "Connections",
          "type": "array"
        },
        "checks": {
          "items": {
            "$ref": "#/$defs/SetupCheck"
          },
          "title": "Checks",
          "type": "array"
        }
      },
      "required": [
        "providers",
        "provider_types",
        "connections",
        "checks"
      ],
      "title": "Configuration",
      "type": "object"
    }
    ```
