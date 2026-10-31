<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationPersonPage

[All wire models](index.md)

Model aliases: `OrganizationPersonPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`OrganizationPerson`](organizationperson.md) | Yes | Not specified |
| `total` | `integer` | Yes | Not specified |
| `page` | `integer` | Yes | Not specified |
| `page_size` | `integer` | Yes | Not specified |
| `pages` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### items

- Maximum items: `50`

### total

- Minimum: `0`

### page

- Minimum: `1`

### page_size

- Minimum: `1`
- Maximum: `50`

### pages

- Minimum: `0`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "items": {
          "items": {
            "$ref": "#/$defs/OrganizationPerson"
          },
          "maxItems": 50,
          "title": "Items",
          "type": "array"
        },
        "total": {
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
          "maximum": 50,
          "minimum": 1,
          "title": "Page Size",
          "type": "integer"
        },
        "pages": {
          "minimum": 0,
          "title": "Pages",
          "type": "integer"
        }
      },
      "required": [
        "items",
        "total",
        "page",
        "page_size",
        "pages"
      ],
      "title": "OrganizationPersonPage",
      "type": "object"
    }
    ```
