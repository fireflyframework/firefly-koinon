<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# TableCoordinateSelection

[All wire models](index.md)

Model aliases: `TableCoordinateSelection`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `manifest` | [`TableCoordinateManifest`](tablecoordinatemanifest.md) | Yes | Not specified |
| `items` | Array of [`CoordinateSourceCell`](coordinatesourcecell.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### items

- Maximum items: `1000`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "manifest": {
          "$ref": "#/$defs/TableCoordinateManifest"
        },
        "items": {
          "items": {
            "$ref": "#/$defs/CoordinateSourceCell"
          },
          "maxItems": 1000,
          "title": "Items",
          "type": "array"
        }
      },
      "required": [
        "manifest",
        "items"
      ],
      "title": "TableCoordinateSelection",
      "type": "object"
    }
    ```
