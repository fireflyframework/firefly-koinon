<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceDestinationPresentation

[All wire models](index.md)

Model aliases: `SourceDestinationPresentation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `segments` | Array of [`SourceDestinationSegment`](sourcedestinationsegment.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### segments

- Maximum items: `256`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "segments": {
          "items": {
            "$ref": "#/$defs/SourceDestinationSegment"
          },
          "maxItems": 256,
          "title": "Segments",
          "type": "array"
        }
      },
      "required": [
        "segments"
      ],
      "title": "SourceDestinationPresentation",
      "type": "object"
    }
    ```
