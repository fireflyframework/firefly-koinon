<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ConversationIdentity

[All wire models](index.md)

Model aliases: `ConversationIdentity`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `product_name` | `string` | Yes | Not specified |
| `assistant_name` | `string` | Yes | Not specified |
| `branding_revision` | `integer` | Yes | Not specified |
| `branding_origin` | `string` | Yes | Not specified |
| `branding_sha256` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### product_name

- Minimum length: `1`
- Maximum length: `64`

### assistant_name

- Minimum length: `1`
- Maximum length: `64`

### branding_revision

- Minimum: `0`
- Maximum: `2147483647`

### branding_origin

- Allowed values: `"deployment"`, `"organization"`

### branding_sha256

- Pattern: `"^[a-f0-9]{64}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "product_name": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Product Name",
          "type": "string"
        },
        "assistant_name": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Assistant Name",
          "type": "string"
        },
        "branding_revision": {
          "maximum": 2147483647,
          "minimum": 0,
          "title": "Branding Revision",
          "type": "integer"
        },
        "branding_origin": {
          "enum": [
            "deployment",
            "organization"
          ],
          "title": "Branding Origin",
          "type": "string"
        },
        "branding_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Branding Sha256",
          "type": "string"
        }
      },
      "required": [
        "product_name",
        "assistant_name",
        "branding_revision",
        "branding_origin",
        "branding_sha256"
      ],
      "title": "ConversationIdentity",
      "type": "object"
    }
    ```
