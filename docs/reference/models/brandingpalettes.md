<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# BrandingPalettes

[All wire models](index.md)

Model aliases: `BrandingPalettes`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `light` | [`BrandingPalette`](brandingpalette.md) | No | Not specified |
| `dark` | [`BrandingPalette`](brandingpalette.md) | No | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "light": {
          "$ref": "#/$defs/BrandingPalette"
        },
        "dark": {
          "$ref": "#/$defs/BrandingPalette"
        }
      },
      "title": "BrandingPalettes",
      "type": "object"
    }
    ```
