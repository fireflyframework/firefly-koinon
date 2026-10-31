<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalReviewInput

[All wire models](index.md)

Model aliases: `ExternalReviewInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `action` | `string` | Yes | Not specified |
| `destination_id` | `string` | Yes | Not specified |
| `target_item_id` | `string` or `null` | No | `null` |
| `expected_version` | `integer` or `null` | No | `null` |
| `content` | [`KnowledgeContent`](knowledgecontent.md) | Yes | Not specified |
| `source_receipt_ids` | Array of `string` | No | `[]` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### action

- Allowed values: `"create_draft"`, `"create_published"`, `"update_draft"`, `"update_published"`, `"publish_draft"`

### destination_id

- Minimum length: `1`
- Maximum length: `64`

### target_item_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### expected_version

- anyOf branch 1 (`integer`): Minimum: `1`

### source_receipt_ids

- Maximum items: `32`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "action": {
          "enum": [
            "create_draft",
            "create_published",
            "update_draft",
            "update_published",
            "publish_draft"
          ],
          "title": "Action",
          "type": "string"
        },
        "destination_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Destination Id",
          "type": "string"
        },
        "target_item_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Target Item Id"
        },
        "expected_version": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Version"
        },
        "content": {
          "$ref": "#/$defs/KnowledgeContent"
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
        "action",
        "destination_id",
        "content"
      ],
      "title": "ExternalReviewInput",
      "type": "object"
    }
    ```
