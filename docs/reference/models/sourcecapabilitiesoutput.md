<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceCapabilitiesOutput

[All wire models](index.md)

Model aliases: `SourceCapabilitiesOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `accounts_available` | `boolean` | Yes | Not specified |
| `inbound_only` | `boolean` | No | `true` |
| `synchronization_available` | `boolean` | Yes | Not specified |
| `providers` | Array of [`SourceProviderCapability`](sourceprovidercapability.md) | Yes | Not specified |
| `modes` | Array of `string` | Yes | Not specified |
| `formats` | Array of [`SourceFormatCapability`](sourceformatcapability.md) | Yes | Not specified |
| `schedule` | [`SourceScheduleCapability`](sourceschedulecapability.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### inbound_only

- Exact value: `true`

### modes

- Each item: Allowed values: `"document"`, `"dataset"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "accounts_available": {
          "title": "Accounts Available",
          "type": "boolean"
        },
        "inbound_only": {
          "const": true,
          "default": true,
          "title": "Inbound Only",
          "type": "boolean"
        },
        "synchronization_available": {
          "title": "Synchronization Available",
          "type": "boolean"
        },
        "providers": {
          "items": {
            "$ref": "#/$defs/SourceProviderCapability"
          },
          "title": "Providers",
          "type": "array"
        },
        "modes": {
          "items": {
            "enum": [
              "document",
              "dataset"
            ],
            "type": "string"
          },
          "title": "Modes",
          "type": "array"
        },
        "formats": {
          "items": {
            "$ref": "#/$defs/SourceFormatCapability"
          },
          "title": "Formats",
          "type": "array"
        },
        "schedule": {
          "$ref": "#/$defs/SourceScheduleCapability"
        }
      },
      "required": [
        "accounts_available",
        "synchronization_available",
        "providers",
        "modes",
        "formats",
        "schedule"
      ],
      "title": "SourceCapabilitiesOutput",
      "type": "object"
    }
    ```
