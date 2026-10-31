<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentFormat

[All wire models](index.md)

Model aliases: `AttachmentFormat`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `media_type` | `string` | Yes | Not specified |
| `extensions` | Array of `string` | Yes | Not specified |
| `extraction` | [`AttachmentObservation`](attachmentobservation.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"document"`, `"image"`, `"bundle"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "kind": {
          "enum": [
            "document",
            "image",
            "bundle"
          ],
          "title": "Kind",
          "type": "string"
        },
        "media_type": {
          "title": "Media Type",
          "type": "string"
        },
        "extensions": {
          "items": {
            "type": "string"
          },
          "title": "Extensions",
          "type": "array"
        },
        "extraction": {
          "$ref": "#/$defs/AttachmentObservation"
        }
      },
      "required": [
        "kind",
        "media_type",
        "extensions",
        "extraction"
      ],
      "title": "AttachmentFormat",
      "type": "object"
    }
    ```
