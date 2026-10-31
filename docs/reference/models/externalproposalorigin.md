<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalProposalOrigin

[All wire models](index.md)

Model aliases: `ExternalProposalOrigin`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `source_receipt_ids` | Array of `string` | No | `[]` |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Exact value: `"external_proposal"`

### source_receipt_ids

- Maximum items: `32`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "kind": {
          "const": "external_proposal",
          "title": "Kind",
          "type": "string"
        },
        "source_receipt_ids": {
          "default": [],
          "items": {
            "maxLength": 64,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 32,
          "title": "Source Receipt Ids",
          "type": "array"
        }
      },
      "required": [
        "kind"
      ],
      "title": "ExternalProposalOrigin",
      "type": "object"
    }
    ```
