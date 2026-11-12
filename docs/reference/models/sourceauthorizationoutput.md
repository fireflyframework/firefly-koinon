<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceAuthorizationOutput

[All wire models](index.md)

Model aliases: `SourceAuthorizationOutput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `connection_id` | `string` | Yes | Not specified |
| `challenge_id` | `string` | Yes | Not specified |
| `authorization_url` | `string` | Yes | Not specified |
| `callback_uri` | `string` | Yes | Not specified |
| `expires_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### callback_uri

- Maximum length: `2048`

### expires_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "connection_id": {
          "title": "Connection Id",
          "type": "string"
        },
        "challenge_id": {
          "title": "Challenge Id",
          "type": "string"
        },
        "authorization_url": {
          "title": "Authorization Url",
          "type": "string"
        },
        "callback_uri": {
          "maxLength": 2048,
          "title": "Callback Uri",
          "type": "string"
        },
        "expires_at": {
          "format": "date-time",
          "title": "Expires At",
          "type": "string"
        }
      },
      "required": [
        "connection_id",
        "challenge_id",
        "authorization_url",
        "callback_uri",
        "expires_at"
      ],
      "title": "SourceAuthorizationOutput",
      "type": "object"
    }
    ```
