<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProcessingRequest

[All wire models](index.md)

Model aliases: `ProcessingRequest`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `page` | `integer` | No | `1` |
| `page_size` | `integer` | No | `25` |
| `workspace_id` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### page

- Minimum: `1`
- Maximum: `100000`

### page_size

- Minimum: `1`
- Maximum: `50`

### workspace_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "page": {
          "default": 1,
          "maximum": 100000,
          "minimum": 1,
          "title": "Page",
          "type": "integer"
        },
        "page_size": {
          "default": 25,
          "maximum": 50,
          "minimum": 1,
          "title": "Page Size",
          "type": "integer"
        },
        "workspace_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Workspace Id"
        }
      },
      "title": "ProcessingRequest",
      "type": "object"
    }
    ```
