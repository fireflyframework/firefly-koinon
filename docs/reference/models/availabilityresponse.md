<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AvailabilityResponse

[All wire models](index.md)

Model aliases: `AvailabilityResponse`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `observed_at` | `string` | Yes | Not specified |
| `items` | Map of string keys to [`AssetAvailability`](assetavailability.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### observed_at

- Format: `"date-time"`

### items

- Additional properties: [`AssetAvailability`](assetavailability.md)


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "observed_at": {
          "format": "date-time",
          "title": "Observed At",
          "type": "string"
        },
        "items": {
          "additionalProperties": {
            "$ref": "#/$defs/AssetAvailability"
          },
          "title": "Items",
          "type": "object"
        }
      },
      "required": [
        "observed_at",
        "items"
      ],
      "title": "AvailabilityResponse",
      "type": "object"
    }
    ```
