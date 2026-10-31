<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IndexActivateInput

[All wire models](index.md)

Model aliases: `IndexActivateInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `expected_active_id` | `string` or `null` | Yes | Not specified |
| `expected_connection_revision` | `integer` or `null` | Yes | Not specified |
| `recovery` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`

### expected_active_id

- anyOf branch 1 (`string`): Maximum length: `64`

### expected_connection_revision

- anyOf branch 1 (`integer`): Minimum: `1`

### recovery

- anyOf branch 1 (`string`): Allowed values: `"finish"`, `"restore_previous"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
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
        "recovery": {
          "anyOf": [
            {
              "enum": [
                "finish",
                "restore_previous"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Recovery"
        }
      },
      "required": [
        "expected_revision",
        "expected_active_id",
        "expected_connection_revision"
      ],
      "title": "IndexActivateInput",
      "type": "object"
    }
    ```
