<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentPromotionView

[All wire models](index.md)

Model aliases: `AttachmentPromotionView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `promotion_id` | `string` | Yes | Not specified |
| `attachment_id` | `string` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |
| `source` | [`PromotedCatalogEntry`](promotedcatalogentry.md) or `null` | No | `null` |
| `assets` | Array of [`PromotedCatalogEntry`](promotedcatalogentry.md) | No | Not specified |
| `asset` | [`PromotedCatalogEntry`](promotedcatalogentry.md) or `null` | No | `null` |
| `table` | [`PromotedCatalogEntry`](promotedcatalogentry.md) or `null` | No | `null` |
| `version` | [`PromotedCatalogEntry`](promotedcatalogentry.md) or `null` | No | `null` |
| `effects` | Map of string keys to [`JsonValue`](jsonvalue.md) | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### action

- Allowed values: `"add"`, `"replace_document"`, `"replace_table"`

### effects

- Additional properties: [`JsonValue`](jsonvalue.md)


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "promotion_id": {
          "title": "Promotion Id",
          "type": "string"
        },
        "attachment_id": {
          "title": "Attachment Id",
          "type": "string"
        },
        "action": {
          "enum": [
            "add",
            "replace_document",
            "replace_table"
          ],
          "title": "Action",
          "type": "string"
        },
        "source": {
          "anyOf": [
            {
              "$ref": "#/$defs/PromotedCatalogEntry"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "assets": {
          "items": {
            "$ref": "#/$defs/PromotedCatalogEntry"
          },
          "title": "Assets",
          "type": "array"
        },
        "asset": {
          "anyOf": [
            {
              "$ref": "#/$defs/PromotedCatalogEntry"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "table": {
          "anyOf": [
            {
              "$ref": "#/$defs/PromotedCatalogEntry"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "version": {
          "anyOf": [
            {
              "$ref": "#/$defs/PromotedCatalogEntry"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "effects": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Effects",
          "type": "object"
        }
      },
      "required": [
        "promotion_id",
        "attachment_id",
        "action"
      ],
      "title": "AttachmentPromotionView",
      "type": "object"
    }
    ```
