<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentEvidence

[All wire models](index.md)

Model aliases: `AttachmentEvidence`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `attachments` | Array of [`AttachmentEvidenceItem`](attachmentevidenceitem.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "attachments": {
          "items": {
            "$ref": "#/$defs/AttachmentEvidenceItem"
          },
          "title": "Attachments",
          "type": "array"
        }
      },
      "required": [
        "attachments"
      ],
      "title": "AttachmentEvidence",
      "type": "object"
    }
    ```
