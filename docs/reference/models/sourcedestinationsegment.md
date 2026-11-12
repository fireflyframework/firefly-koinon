<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceDestinationSegment

[All wire models](index.md)

Model aliases: `SourceDestinationSegment`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### name

- Maximum length: `255`


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
        "kind": {
          "title": "Kind",
          "type": "string"
        },
        "name": {
          "maxLength": 255,
          "title": "Name",
          "type": "string"
        }
      },
      "required": [
        "id",
        "kind",
        "name"
      ],
      "title": "SourceDestinationSegment",
      "type": "object"
    }
    ```
