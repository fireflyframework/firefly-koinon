<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# FieldSchema

[All wire models](index.md)

Model aliases: `FieldSchema`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `options` | Array of [`FieldOption`](fieldoption.md) | No | Not specified |
| `name` | `string` | Yes | Not specified |
| `label` | `string` | Yes | Not specified |
| `type` | `string` | Yes | Not specified |
| `required` | `boolean` | Yes | Not specified |
| `write_only` | `boolean` or `null` | No | `null` |
| `default` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### type

- Allowed values: `"text"`, `"url"`, `"secret"`, `"string_list"`, `"select"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "options": {
          "items": {
            "$ref": "#/$defs/FieldOption"
          },
          "title": "Options",
          "type": "array"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "label": {
          "title": "Label",
          "type": "string"
        },
        "type": {
          "enum": [
            "text",
            "url",
            "secret",
            "string_list",
            "select"
          ],
          "title": "Type",
          "type": "string"
        },
        "required": {
          "title": "Required",
          "type": "boolean"
        },
        "write_only": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Write Only"
        },
        "default": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Default"
        }
      },
      "required": [
        "name",
        "label",
        "type",
        "required"
      ],
      "title": "FieldSchema",
      "type": "object"
    }
    ```
