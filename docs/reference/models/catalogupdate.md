<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CatalogUpdate

[All wire models](index.md)

Model aliases: `CatalogUpdate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` or `null` | No | `null` |
| `description` | `string` or `null` | No | `null` |
| `metadata` | Map of string keys to [`JsonValue`](jsonvalue.md) or `null` | No | `null` |
| `expected_updated_at` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### metadata

- anyOf branch 1 (Map of string keys to [`JsonValue`](jsonvalue.md)): Additional properties: [`JsonValue`](jsonvalue.md)

### expected_updated_at

- anyOf branch 1 (`string`): Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Name"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Description"
        },
        "metadata": {
          "anyOf": [
            {
              "additionalProperties": {
                "$ref": "#/$defs/JsonValue"
              },
              "type": "object"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Metadata"
        },
        "expected_updated_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Updated At"
        }
      },
      "title": "CatalogUpdate",
      "type": "object"
    }
    ```
