<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ContentUpdate

[All wire models](index.md)

Model aliases: `ContentUpdate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `asset` | [`CatalogEntry`](catalogentry.md) | Yes | Not specified |
| `source` | [`CatalogEntry`](catalogentry.md) or `null` | No | `null` |
| `table` | [`CatalogEntry`](catalogentry.md) or `null` | No | `null` |
| `version` | [`CatalogEntry`](catalogentry.md) | Yes | Not specified |
| `effects` | [`ContentEffects`](contenteffects.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "asset": {
          "$ref": "#/$defs/CatalogEntry"
        },
        "source": {
          "anyOf": [
            {
              "$ref": "#/$defs/CatalogEntry"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "table": {
          "anyOf": [
            {
              "$ref": "#/$defs/CatalogEntry"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "version": {
          "$ref": "#/$defs/CatalogEntry"
        },
        "effects": {
          "$ref": "#/$defs/ContentEffects"
        }
      },
      "required": [
        "asset",
        "version",
        "effects"
      ],
      "title": "ContentUpdate",
      "type": "object"
    }
    ```
