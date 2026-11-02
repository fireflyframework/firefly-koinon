<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DeliveryObservationPage

[All wire models](index.md)

Model aliases: `DeliveryObservationPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`DeliveryOperationObservation`](deliveryoperationobservation.md) | Yes | Not specified |
| `has_more` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "items": {
          "items": {
            "$ref": "#/$defs/DeliveryOperationObservation"
          },
          "title": "Items",
          "type": "array"
        },
        "has_more": {
          "title": "Has More",
          "type": "boolean"
        }
      },
      "required": [
        "items",
        "has_more"
      ],
      "title": "DeliveryObservationPage",
      "type": "object"
    }
    ```
