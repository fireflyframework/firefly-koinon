<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProductHelpContext

[All wire models](index.md)

Supporting wire definition. It is not a separate public model alias in the canonical manifest.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | No | `"product_configuration"` |
| `product_name` | `string` | Yes | Not specified |
| `assistant_name` | `string` | Yes | Not specified |
| `branding_revision` | `integer` | Yes | Not specified |
| `branding_origin` | `string` | No | `"deployment"` |
| `selection` | `string` | No | `"broader_scope"` |
| `tools` | Array of `string` | No | `[]` |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Exact value: `"product_configuration"`

### product_name

- Minimum length: `1`
- Maximum length: `120`

### assistant_name

- Minimum length: `1`
- Maximum length: `120`

### branding_revision

- Minimum: `0`

### branding_origin

- Allowed values: `"organization"`, `"deployment"`

### selection

- Allowed values: `"explicit_selection"`, `"broader_scope"`, `"private_attachments"`

### tools

- Maximum items: `5`
- Each item: Allowed values: `"search_knowledge"`, `"inspect_schema"`, `"query_dataset"`, `"propose_catalog_update"`, `"search_private_attachments"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "kind": {
          "const": "product_configuration",
          "default": "product_configuration",
          "title": "Kind",
          "type": "string"
        },
        "product_name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Product Name",
          "type": "string"
        },
        "assistant_name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Assistant Name",
          "type": "string"
        },
        "branding_revision": {
          "minimum": 0,
          "title": "Branding Revision",
          "type": "integer"
        },
        "branding_origin": {
          "default": "deployment",
          "enum": [
            "organization",
            "deployment"
          ],
          "title": "Branding Origin",
          "type": "string"
        },
        "selection": {
          "default": "broader_scope",
          "enum": [
            "explicit_selection",
            "broader_scope",
            "private_attachments"
          ],
          "title": "Selection",
          "type": "string"
        },
        "tools": {
          "default": [],
          "items": {
            "enum": [
              "search_knowledge",
              "inspect_schema",
              "query_dataset",
              "propose_catalog_update",
              "search_private_attachments"
            ],
            "type": "string"
          },
          "maxItems": 5,
          "title": "Tools",
          "type": "array"
        }
      },
      "required": [
        "product_name",
        "assistant_name",
        "branding_revision"
      ],
      "title": "ProductHelpContext",
      "type": "object"
    }
    ```
