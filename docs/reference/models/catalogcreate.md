<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CatalogCreate

[All wire models](index.md)

Model aliases: `CatalogCreate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `parent_id` | `string` or `null` | No | `null` |
| `description` | `string` | No | `""` |
| `metadata` | Map of string keys to [`JsonValue`](jsonvalue.md) | No | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### metadata

- Additional properties: [`JsonValue`](jsonvalue.md)


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "title": "Kind",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "parent_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Id"
        },
        "description": {
          "default": "",
          "title": "Description",
          "type": "string"
        },
        "metadata": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Metadata",
          "type": "object"
        }
      },
      "required": [
        "kind",
        "name"
      ],
      "title": "CatalogCreate",
      "type": "object"
    }
    ```
