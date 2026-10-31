<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# TitleSuggestion

[All wire models](index.md)

Model aliases: `TitleSuggestion`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `title` | `string` | Yes | Not specified |
| `based_on_revision` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "title": {
          "title": "Title",
          "type": "string"
        },
        "based_on_revision": {
          "title": "Based On Revision",
          "type": "integer"
        }
      },
      "required": [
        "title",
        "based_on_revision"
      ],
      "title": "TitleSuggestion",
      "type": "object"
    }
    ```
