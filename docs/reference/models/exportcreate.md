<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExportCreate

[All wire models](index.md)

Model aliases: `ExportCreate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `review_id` | `string` | Yes | Not specified |
| `expected_revision` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### review_id

- Minimum length: `1`
- Maximum length: `64`

### expected_revision

- Pattern: `"^[a-f0-9]{64}$"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "review_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Review Id",
          "type": "string"
        },
        "expected_revision": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Expected Revision",
          "type": "string"
        }
      },
      "required": [
        "review_id",
        "expected_revision"
      ],
      "title": "ExportCreate",
      "type": "object"
    }
    ```
