<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MessageSelection

[All wire models](index.md)

Model aliases: `MessageSelection`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `thread_id` | `string` | Yes | Not specified |
| `message_ids` | Array of `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### thread_id

- Minimum length: `1`
- Maximum length: `64`

### message_ids

- Minimum items: `1`
- Maximum items: `200`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "thread_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Thread Id",
          "type": "string"
        },
        "message_ids": {
          "items": {
            "maxLength": 64,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 200,
          "minItems": 1,
          "title": "Message Ids",
          "type": "array"
        }
      },
      "required": [
        "thread_id",
        "message_ids"
      ],
      "title": "MessageSelection",
      "type": "object"
    }
    ```
