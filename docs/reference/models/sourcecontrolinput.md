<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceControlInput

[All wire models](index.md)

Model aliases: `SourceControlInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `operation_id` | `string` | Yes | Not specified |
| `expected_revision` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### operation_id

- Minimum length: `36`
- Maximum length: `36`

### expected_revision

- Minimum: `1`
- Maximum: `2147483646`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "operation_id": {
          "maxLength": 36,
          "minLength": 36,
          "title": "Operation Id",
          "type": "string"
        },
        "expected_revision": {
          "maximum": 2147483646,
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        }
      },
      "required": [
        "operation_id",
        "expected_revision"
      ],
      "title": "SourceControlInput",
      "type": "object"
    }
    ```
