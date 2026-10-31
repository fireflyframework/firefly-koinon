<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryBatchCreate

[All wire models](index.md)

Model aliases: `QueryBatchCreate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `workspace_id` | `string` | Yes | Not specified |
| `processing_policy` | `string` | No | `"independent_nl_v1"` |
| `items` | Array of [`QueryManifestItem`](querymanifestitem.md) | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### workspace_id

- Minimum length: `1`
- Maximum length: `64`

### processing_policy

- Exact value: `"independent_nl_v1"`

### items

- Minimum items: `1`
- Maximum items: `20`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "workspace_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Workspace Id",
          "type": "string"
        },
        "processing_policy": {
          "const": "independent_nl_v1",
          "default": "independent_nl_v1",
          "title": "Processing Policy",
          "type": "string"
        },
        "items": {
          "items": {
            "$ref": "#/$defs/QueryManifestItem"
          },
          "maxItems": 20,
          "minItems": 1,
          "title": "Items",
          "type": "array"
        }
      },
      "required": [
        "workspace_id",
        "items"
      ],
      "title": "QueryBatchCreate",
      "type": "object"
    }
    ```
