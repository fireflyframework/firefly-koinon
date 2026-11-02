<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# BulkRecoveryAction

[All wire models](index.md)

Model aliases: `BulkRecoveryAction`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `operation` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`
- Maximum: `2147483647`

### operation

- Allowed values: `"retry_processing"`, `"finalize_publication"`, `"acknowledge_commit"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "maximum": 2147483647,
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        },
        "operation": {
          "enum": [
            "retry_processing",
            "finalize_publication",
            "acknowledge_commit"
          ],
          "title": "Operation",
          "type": "string"
        }
      },
      "required": [
        "expected_revision",
        "operation"
      ],
      "title": "BulkRecoveryAction",
      "type": "object"
    }
    ```
