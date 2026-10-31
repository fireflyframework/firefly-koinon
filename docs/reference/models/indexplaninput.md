<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IndexPlanInput

[All wire models](index.md)

Model aliases: `IndexPlanInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `workspace_id` | `string` | Yes | Not specified |
| `domain` | `string` | Yes | Not specified |
| `provider_id` | `string` | Yes | Not specified |
| `model_id` | `string` | Yes | Not specified |
| `expected_dimensions` | `integer` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### workspace_id

- Minimum length: `1`
- Maximum length: `64`

### domain

- Allowed values: `"documents"`, `"structured"`

### provider_id

- Minimum length: `1`
- Maximum length: `64`

### model_id

- Minimum length: `1`
- Maximum length: `255`

### expected_dimensions

- anyOf branch 1 (`integer`): Minimum: `64`
- anyOf branch 1 (`integer`): Maximum: `4096`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "workspace_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Workspace Id",
          "type": "string"
        },
        "domain": {
          "enum": [
            "documents",
            "structured"
          ],
          "title": "Domain",
          "type": "string"
        },
        "provider_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Provider Id",
          "type": "string"
        },
        "model_id": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Model Id",
          "type": "string"
        },
        "expected_dimensions": {
          "anyOf": [
            {
              "maximum": 4096,
              "minimum": 64,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Dimensions"
        }
      },
      "required": [
        "workspace_id",
        "domain",
        "provider_id",
        "model_id"
      ],
      "title": "IndexPlanInput",
      "type": "object"
    }
    ```
