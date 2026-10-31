<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DatasetSchema

[All wire models](index.md)

Model aliases: `DatasetSchema`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `tables` | Array of [`SchemaTable`](schematable.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "tables": {
          "items": {
            "$ref": "#/$defs/SchemaTable"
          },
          "title": "Tables",
          "type": "array"
        }
      },
      "required": [
        "tables"
      ],
      "title": "DatasetSchema",
      "type": "object"
    }
    ```
