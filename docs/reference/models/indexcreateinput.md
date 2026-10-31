<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IndexCreateInput

[All wire models](index.md)

Model aliases: `IndexCreateInput`.

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
| `expected_active_id` | `string` or `null` | Yes | Not specified |
| `expected_connection_revision` | `integer` or `null` | Yes | Not specified |
| `batch_size` | `integer` | No | `32` |

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

### expected_active_id

- anyOf branch 1 (`string`): Maximum length: `64`

### expected_connection_revision

- anyOf branch 1 (`integer`): Minimum: `1`

### batch_size

- Minimum: `1`
- Maximum: `64`


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
        },
        "expected_active_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Expected Active Id"
        },
        "expected_connection_revision": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Expected Connection Revision"
        },
        "batch_size": {
          "default": 32,
          "maximum": 64,
          "minimum": 1,
          "title": "Batch Size",
          "type": "integer"
        }
      },
      "required": [
        "workspace_id",
        "domain",
        "provider_id",
        "model_id",
        "expected_active_id",
        "expected_connection_revision"
      ],
      "title": "IndexCreateInput",
      "type": "object"
    }
    ```
