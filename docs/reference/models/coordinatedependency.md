<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CoordinateDependency

[All wire models](index.md)

Model aliases: `CoordinateDependency`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Not specified |
| `version` | `string` or `null` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### name

- Minimum length: `1`
- Maximum length: `512`

### version

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `512`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "name": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "version": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Version"
        }
      },
      "required": [
        "name",
        "version"
      ],
      "title": "CoordinateDependency",
      "type": "object"
    }
    ```
