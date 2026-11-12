<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceReviewPage

[All wire models](index.md)

Model aliases: `SourceReviewPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `review_id` | `string` | Yes | Not specified |
| `validation_id` | `string` or `null` | No | `null` |
| `root_kind` | `string` | No | `"folder"` |
| `policy_revision` | `integer` | Yes | Not specified |
| `review_digest` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |
| `items` | Array of [`SourcePreviewItem`](sourcepreviewitem.md) | Yes | Not specified |
| `next_cursor` | `string` or `null` | Yes | Not specified |
| `enumeration_complete` | `boolean` | Yes | Not specified |
| `total` | `integer` or `null` | Yes | Not specified |
| `observed_count` | `integer` or `null` | Yes | Not specified |
| `known_bytes` | `integer` or `null` | Yes | Not specified |
| `unknown_size_count` | `integer` or `null` | Yes | Not specified |
| `can_apply` | `boolean` | Yes | Not specified |
| `destination` | [`SourceDestinationPresentation`](sourcedestinationpresentation.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### review_id

- Minimum length: `1`
- Maximum length: `64`

### validation_id

- anyOf branch 1 (`string`): Format: `"uuid"`

### root_kind

- Allowed values: `"file"`, `"folder"`

### review_digest

- Pattern: `"^[a-f0-9]{64}$"`

### expires_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "review_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Review Id",
          "type": "string"
        },
        "validation_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Validation Id"
        },
        "root_kind": {
          "default": "folder",
          "enum": [
            "file",
            "folder"
          ],
          "title": "Root Kind",
          "type": "string"
        },
        "policy_revision": {
          "title": "Policy Revision",
          "type": "integer"
        },
        "review_digest": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Review Digest",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        },
        "items": {
          "items": {
            "$ref": "#/$defs/SourcePreviewItem"
          },
          "title": "Items",
          "type": "array"
        },
        "next_cursor": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Next Cursor"
        },
        "enumeration_complete": {
          "title": "Enumeration Complete",
          "type": "boolean"
        },
        "total": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Total"
        },
        "observed_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Observed Count"
        },
        "known_bytes": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Known Bytes"
        },
        "unknown_size_count": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Unknown Size Count"
        },
        "can_apply": {
          "title": "Can Apply",
          "type": "boolean"
        },
        "destination": {
          "$ref": "#/$defs/SourceDestinationPresentation"
        }
      },
      "required": [
        "review_id",
        "policy_revision",
        "review_digest",
        "expires_at",
        "items",
        "next_cursor",
        "enumeration_complete",
        "total",
        "observed_count",
        "known_bytes",
        "unknown_size_count",
        "can_apply",
        "destination"
      ],
      "title": "SourceReviewPage",
      "type": "object"
    }
    ```
