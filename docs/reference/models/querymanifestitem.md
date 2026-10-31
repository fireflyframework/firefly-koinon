<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# QueryManifestItem

[All wire models](index.md)

Model aliases: `QueryManifestItem`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `client_item_id` | `string` | Yes | Not specified |
| `dataset_id` | `string` | Yes | Not specified |
| `question` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### client_item_id

- Minimum length: `1`
- Maximum length: `64`

### dataset_id

- Minimum length: `1`
- Maximum length: `64`

### question

- Minimum length: `1`
- Maximum length: `8000`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "client_item_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Client Item Id",
          "type": "string"
        },
        "dataset_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Dataset Id",
          "type": "string"
        },
        "question": {
          "maxLength": 8000,
          "minLength": 1,
          "title": "Question",
          "type": "string"
        }
      },
      "required": [
        "client_item_id",
        "dataset_id",
        "question"
      ],
      "title": "QueryManifestItem",
      "type": "object"
    }
    ```
