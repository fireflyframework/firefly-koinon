<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalFileCleanupReview

[All wire models](index.md)

Model aliases: `ExternalFileCleanupReview`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `processed_objects` | `integer` | Yes | Not specified |
| `total_objects` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### status

- Allowed values: `"purging"`, `"purged"`

### processed_objects

- Minimum: `0`
- Maximum: `2049`

### total_objects

- Minimum: `1`
- Maximum: `2049`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "status": {
          "enum": [
            "purging",
            "purged"
          ],
          "title": "Status",
          "type": "string"
        },
        "processed_objects": {
          "maximum": 2049,
          "minimum": 0,
          "title": "Processed Objects",
          "type": "integer"
        },
        "total_objects": {
          "maximum": 2049,
          "minimum": 1,
          "title": "Total Objects",
          "type": "integer"
        }
      },
      "required": [
        "id",
        "status",
        "processed_objects",
        "total_objects"
      ],
      "title": "ExternalFileCleanupReview",
      "type": "object"
    }
    ```
