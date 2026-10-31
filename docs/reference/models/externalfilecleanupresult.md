<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalFileCleanupResult

[All wire models](index.md)

Model aliases: `ExternalFileCleanupResult`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `reviews` | Array of [`ExternalFileCleanupReview`](externalfilecleanupreview.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### reviews

- Maximum items: `25`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "reviews": {
          "items": {
            "$ref": "#/$defs/ExternalFileCleanupReview"
          },
          "maxItems": 25,
          "title": "Reviews",
          "type": "array"
        }
      },
      "required": [
        "reviews"
      ],
      "title": "ExternalFileCleanupResult",
      "type": "object"
    }
    ```
