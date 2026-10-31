<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentCapabilities

[All wire models](index.md)

Model aliases: `AttachmentCapabilities`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `storage` | [`AttachmentObservation`](attachmentobservation.md) | Yes | Not specified |
| `database` | [`AttachmentObservation`](attachmentobservation.md) | Yes | Not specified |
| `extraction` | [`AttachmentObservation`](attachmentobservation.md) | Yes | Not specified |
| `limits` | [`AttachmentLimits`](attachmentlimits.md) | Yes | Not specified |
| `formats` | Array of [`AttachmentFormat`](attachmentformat.md) | Yes | Not specified |
| `promotion` | [`AttachmentPromotionRequirements`](attachmentpromotionrequirements.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "storage": {
          "$ref": "#/$defs/AttachmentObservation"
        },
        "database": {
          "$ref": "#/$defs/AttachmentObservation"
        },
        "extraction": {
          "$ref": "#/$defs/AttachmentObservation"
        },
        "limits": {
          "$ref": "#/$defs/AttachmentLimits"
        },
        "formats": {
          "items": {
            "$ref": "#/$defs/AttachmentFormat"
          },
          "title": "Formats",
          "type": "array"
        },
        "promotion": {
          "$ref": "#/$defs/AttachmentPromotionRequirements"
        }
      },
      "required": [
        "storage",
        "database",
        "extraction",
        "limits",
        "formats",
        "promotion"
      ],
      "title": "AttachmentCapabilities",
      "type": "object"
    }
    ```
