<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ResultPin

[All wire models](index.md)

Supporting wire definition. It is not a separate public model alias in the canonical manifest.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`


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
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
          "type": "string"
        }
      },
      "required": [
        "id",
        "sha256"
      ],
      "title": "ResultPin",
      "type": "object"
    }
    ```
