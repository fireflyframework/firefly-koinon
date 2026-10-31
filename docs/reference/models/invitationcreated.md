<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# InvitationCreated

[All wire models](index.md)

Model aliases: `InvitationCreated`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `invitation` | [`Invitation`](invitation.md) | Yes | Not specified |
| `token` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### token

- Format: `"password"`
- Write only: `true`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "invitation": {
          "$ref": "#/$defs/Invitation"
        },
        "token": {
          "format": "password",
          "title": "Token",
          "type": "string",
          "writeOnly": true
        }
      },
      "required": [
        "invitation",
        "token"
      ],
      "title": "InvitationCreated",
      "type": "object"
    }
    ```
