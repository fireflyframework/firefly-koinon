<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpRegisteredClient

[All wire models](index.md)

Model aliases: `McpRegisteredClient`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `client_id` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `scopes` | Array of `string` | Yes | Not specified |
| `client_auth` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### client_auth

- Allowed values: `"public"`, `"confidential"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "client_id": {
          "title": "Client Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "scopes": {
          "items": {
            "type": "string"
          },
          "title": "Scopes",
          "type": "array"
        },
        "client_auth": {
          "enum": [
            "public",
            "confidential"
          ],
          "title": "Client Auth",
          "type": "string"
        }
      },
      "required": [
        "client_id",
        "name",
        "scopes",
        "client_auth"
      ],
      "title": "McpRegisteredClient",
      "type": "object"
    }
    ```
