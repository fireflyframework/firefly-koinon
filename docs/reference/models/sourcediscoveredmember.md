<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceDiscoveredMember

[All wire models](index.md)

Model aliases: `SourceDiscoveredMember`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `locator` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `ambiguous` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### locator

- Maximum length: `2048`

### name

- Maximum length: `255`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "locator": {
          "maxLength": 2048,
          "title": "Locator",
          "type": "string"
        },
        "name": {
          "maxLength": 255,
          "title": "Name",
          "type": "string"
        },
        "ambiguous": {
          "title": "Ambiguous",
          "type": "boolean"
        }
      },
      "required": [
        "locator",
        "name",
        "ambiguous"
      ],
      "title": "SourceDiscoveredMember",
      "type": "object"
    }
    ```
