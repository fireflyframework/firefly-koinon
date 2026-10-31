<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpOAuthClientCredential

[All wire models](index.md)

Model aliases: `McpOAuthClientCredential`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `client` | [`McpOAuthClient`](mcpoauthclient.md) | Yes | Not specified |
| `client_secret` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "client": {
          "$ref": "#/$defs/McpOAuthClient"
        },
        "client_secret": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Client Secret"
        }
      },
      "required": [
        "client"
      ],
      "title": "McpOAuthClientCredential",
      "type": "object"
    }
    ```
