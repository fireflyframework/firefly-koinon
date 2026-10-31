<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Capabilities

[All wire models](index.md)

Model aliases: `Capabilities`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `attachments` | [`AttachmentCapabilities`](attachmentcapabilities.md) or `null` | No | `null` |
| `catalog` | [`CatalogCapability`](catalogcapability.md) or `null` | No | `null` |
| `agentic` | [`AgenticCapability`](agenticcapability.md) or `null` | No | `null` |
| `domains` | Map of string keys to [`DomainCapability`](domaincapability.md) | No | Not specified |
| `providers` | Array of [`ProviderCapability`](providercapability.md) | Yes | Not specified |
| `features` | Array of [`FeatureCapability`](featurecapability.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### domains

- Additional properties: [`DomainCapability`](domaincapability.md)


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "attachments": {
          "anyOf": [
            {
              "$ref": "#/$defs/AttachmentCapabilities"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "catalog": {
          "anyOf": [
            {
              "$ref": "#/$defs/CatalogCapability"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "agentic": {
          "anyOf": [
            {
              "$ref": "#/$defs/AgenticCapability"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "domains": {
          "additionalProperties": {
            "$ref": "#/$defs/DomainCapability"
          },
          "title": "Domains",
          "type": "object"
        },
        "providers": {
          "items": {
            "$ref": "#/$defs/ProviderCapability"
          },
          "title": "Providers",
          "type": "array"
        },
        "features": {
          "items": {
            "$ref": "#/$defs/FeatureCapability"
          },
          "title": "Features",
          "type": "array"
        }
      },
      "required": [
        "providers",
        "features"
      ],
      "title": "Capabilities",
      "type": "object"
    }
    ```
