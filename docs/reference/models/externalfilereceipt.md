<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalFileReceipt

[All wire models](index.md)

Model aliases: `ExternalFileReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `source` | [`ExternalFileCatalogEntry`](externalfilecatalogentry.md) | Yes | Not specified |
| `assets` | Array of [`ExternalFileCatalogEntry`](externalfilecatalogentry.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### assets

- Minimum items: `1`
- Maximum items: `128`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "source": {
          "$ref": "#/$defs/ExternalFileCatalogEntry"
        },
        "assets": {
          "items": {
            "$ref": "#/$defs/ExternalFileCatalogEntry"
          },
          "maxItems": 128,
          "minItems": 1,
          "title": "Assets",
          "type": "array"
        }
      },
      "required": [
        "source",
        "assets"
      ],
      "title": "ExternalFileReceipt",
      "type": "object"
    }
    ```
