<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CoordinatePage

[All wire models](index.md)

Model aliases: `CoordinatePage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `manifest` | [`TableCoordinateManifest`](tablecoordinatemanifest.md) | Yes | Not specified |
| `total` | `integer` | Yes | Not specified |
| `page` | `integer` | Yes | Not specified |
| `page_size` | `integer` | Yes | Not specified |
| `pages` | `integer` | Yes | Not specified |
| `has_next` | `boolean` | Yes | Not specified |
| `has_previous` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### total

- Minimum: `0`
- Maximum: `9007199254740991`

### page

- Minimum: `1`

### page_size

- Minimum: `1`
- Maximum: `100`

### pages

- Minimum: `0`
- Maximum: `9007199254740991`


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
        "total": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Total",
          "type": "integer"
        },
        "page": {
          "minimum": 1,
          "title": "Page",
          "type": "integer"
        },
        "page_size": {
          "maximum": 100,
          "minimum": 1,
          "title": "Page Size",
          "type": "integer"
        },
        "pages": {
          "maximum": 9007199254740991,
          "minimum": 0,
          "title": "Pages",
          "type": "integer"
        },
        "has_next": {
          "title": "Has Next",
          "type": "boolean"
        },
        "has_previous": {
          "title": "Has Previous",
          "type": "boolean"
        }
      },
      "required": [
        "manifest",
        "total",
        "page",
        "page_size",
        "pages",
        "has_next",
        "has_previous"
      ],
      "title": "CoordinatePage",
      "type": "object"
    }
    ```
