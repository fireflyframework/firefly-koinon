<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# InvitationToken

[All wire models](index.md)

Model aliases: `InvitationToken`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `token` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### token

- Format: `"password"`
- Write only: `true`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "token": {
          "format": "password",
          "title": "Token",
          "type": "string",
          "writeOnly": true
        }
      },
      "required": [
        "token"
      ],
      "title": "InvitationToken",
      "type": "object"
    }
    ```
