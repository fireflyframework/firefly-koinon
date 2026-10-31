<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalReviewView

[All wire models](index.md)

Model aliases: `ExternalReviewView`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `review` | [`KnowledgeIntent`](knowledgeintent.md) | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### status

- Allowed values: `"preview"`, `"committing"`, `"committed"`, `"cancelled"`, `"stale"`, `"unresolved"`

### expires_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "review": {
          "$ref": "#/$defs/KnowledgeIntent"
        },
        "status": {
          "enum": [
            "preview",
            "committing",
            "committed",
            "cancelled",
            "stale",
            "unresolved"
          ],
          "title": "Status",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "review",
        "status",
        "expires_at"
      ],
      "title": "ExternalReviewView",
      "type": "object"
    }
    ```
