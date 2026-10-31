<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeRoles

[All wire models](index.md)

Model aliases: `KnowledgeRoles`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `roles` | Array of [`KnowledgeRole`](knowledgerole.md) | Yes | Not specified |
| `model_options_schema` | Map of string keys to [`JsonValue`](jsonvalue.md) | No | Not specified |
| `providers` | Array of [`KnowledgeProvider`](knowledgeprovider.md) or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### model_options_schema

- Additional properties: [`JsonValue`](jsonvalue.md)


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "roles": {
          "items": {
            "$ref": "#/$defs/KnowledgeRole"
          },
          "title": "Roles",
          "type": "array"
        },
        "model_options_schema": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Model Options Schema",
          "type": "object"
        },
        "providers": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/KnowledgeProvider"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Providers"
        }
      },
      "required": [
        "roles"
      ],
      "title": "KnowledgeRoles",
      "type": "object"
    }
    ```
