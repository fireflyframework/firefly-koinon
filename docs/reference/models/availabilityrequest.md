<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AvailabilityRequest

[All wire models](index.md)

Model aliases: `AvailabilityRequest`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `asset_ids` | Array of `string` | Yes | Not specified |
| `workspace_id` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### asset_ids

- Minimum items: `1`
- Maximum items: `100`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`

### workspace_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "asset_ids": {
          "items": {
            "maxLength": 64,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 100,
          "minItems": 1,
          "title": "Asset Ids",
          "type": "array"
        },
        "workspace_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Workspace Id"
        }
      },
      "required": [
        "asset_ids"
      ],
      "title": "AvailabilityRequest",
      "type": "object"
    }
    ```
