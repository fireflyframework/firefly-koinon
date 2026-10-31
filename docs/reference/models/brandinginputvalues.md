<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# BrandingInputValues

[All wire models](index.md)

Model aliases: `BrandingInputValues`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `product_name` | `string` | No | `"koinon"` |
| `assistant_name` | `string` | No | `"koinon"` |
| `logo_light` | `string` or `null` | No | `null` |
| `logo_dark` | `string` or `null` | No | `null` |
| `symbol` | `string` or `null` | No | `null` |
| `favicon` | `string` or `null` | No | `null` |
| `palette` | [`BrandingPalettes`](brandingpalettes.md) | No | Not specified |
| `font_family` | `string` | No | `"Manrope"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### product_name

- Minimum length: `1`
- Maximum length: `64`

### assistant_name

- Minimum length: `1`
- Maximum length: `64`

### logo_light

- anyOf branch 1 (`string`): Maximum length: `349550`

### logo_dark

- anyOf branch 1 (`string`): Maximum length: `349550`

### symbol

- anyOf branch 1 (`string`): Maximum length: `349550`

### favicon

- anyOf branch 1 (`string`): Maximum length: `349550`

### font_family

- Allowed values: `"Manrope"`, `"Inter"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "product_name": {
          "default": "koinon",
          "maxLength": 64,
          "minLength": 1,
          "title": "Product Name",
          "type": "string"
        },
        "assistant_name": {
          "default": "koinon",
          "maxLength": 64,
          "minLength": 1,
          "title": "Assistant Name",
          "type": "string"
        },
        "logo_light": {
          "anyOf": [
            {
              "maxLength": 349550,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Logo Light"
        },
        "logo_dark": {
          "anyOf": [
            {
              "maxLength": 349550,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Logo Dark"
        },
        "symbol": {
          "anyOf": [
            {
              "maxLength": 349550,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Symbol"
        },
        "favicon": {
          "anyOf": [
            {
              "maxLength": 349550,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Favicon"
        },
        "palette": {
          "$ref": "#/$defs/BrandingPalettes"
        },
        "font_family": {
          "default": "Manrope",
          "enum": [
            "Manrope",
            "Inter"
          ],
          "title": "Font Family",
          "type": "string"
        }
      },
      "title": "BrandingInputValues",
      "type": "object"
    }
    ```
