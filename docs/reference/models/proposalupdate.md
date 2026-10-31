<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProposalUpdate

[All wire models](index.md)

Model aliases: `ProposalUpdate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"applied"`, `"cancelled"`

### revision

- Minimum: `2`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "status": {
          "enum": [
            "applied",
            "cancelled"
          ],
          "title": "Status",
          "type": "string"
        },
        "revision": {
          "minimum": 2,
          "title": "Revision",
          "type": "integer"
        }
      },
      "required": [
        "id",
        "status",
        "revision"
      ],
      "title": "ProposalUpdate",
      "type": "object"
    }
    ```
