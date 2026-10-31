<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AuthorSummary

[All wire models](index.md)

Model aliases: `AuthorSummary`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `subject` | `string` | Yes | Not specified |
| `display_name` | `string` | Yes | Not specified |
| `avatar_data_url` | `string` or `null` | No | `null` |
| `avatar_version` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "subject": {
          "title": "Subject",
          "type": "string"
        },
        "display_name": {
          "title": "Display Name",
          "type": "string"
        },
        "avatar_data_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Avatar Data Url"
        },
        "avatar_version": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Avatar Version"
        }
      },
      "required": [
        "subject",
        "display_name"
      ],
      "title": "AuthorSummary",
      "type": "object"
    }
    ```
