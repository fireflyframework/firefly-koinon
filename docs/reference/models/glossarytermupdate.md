<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GlossaryTermUpdate

[All wire models](index.md)

Model aliases: `GlossaryTermUpdate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `definition` | `string` or `null` | No | `null` |
| `synonyms` | Array of `string` or `null` | No | `null` |
| `tags` | Array of `string` or `null` | No | `null` |
| `related_columns` | Array of `string` or `null` | No | `null` |
| `related_metrics` | Array of `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### definition

- anyOf branch 1 (`string`): Maximum length: `16000`

### synonyms

- anyOf branch 1 (Array of `string`): Maximum items: `64`
- anyOf branch 1 (Array of `string`): Each item: Maximum length: `512`

### tags

- anyOf branch 1 (Array of `string`): Maximum items: `64`
- anyOf branch 1 (Array of `string`): Each item: Maximum length: `512`

### related_columns

- anyOf branch 1 (Array of `string`): Maximum items: `64`
- anyOf branch 1 (Array of `string`): Each item: Maximum length: `512`

### related_metrics

- anyOf branch 1 (Array of `string`): Maximum items: `64`
- anyOf branch 1 (Array of `string`): Each item: Maximum length: `512`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "definition": {
          "anyOf": [
            {
              "maxLength": 16000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Definition"
        },
        "synonyms": {
          "anyOf": [
            {
              "items": {
                "maxLength": 512,
                "type": "string"
              },
              "maxItems": 64,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Synonyms"
        },
        "tags": {
          "anyOf": [
            {
              "items": {
                "maxLength": 512,
                "type": "string"
              },
              "maxItems": 64,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Tags"
        },
        "related_columns": {
          "anyOf": [
            {
              "items": {
                "maxLength": 512,
                "type": "string"
              },
              "maxItems": 64,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Related Columns"
        },
        "related_metrics": {
          "anyOf": [
            {
              "items": {
                "maxLength": 512,
                "type": "string"
              },
              "maxItems": 64,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Related Metrics"
        }
      },
      "title": "GlossaryTermUpdate",
      "type": "object"
    }
    ```
