<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpConnectionDescriptor

[All wire models](index.md)

Model aliases: `McpConnectionDescriptor`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `enabled` | `boolean` | Yes | Not specified |
| `local_only` | `boolean` | No | `false` |
| `endpoint` | `string` or `null` | Yes | Not specified |
| `transport` | `string` | No | `"streamable-http"` |
| `authentication` | Array of `string` | Yes | Not specified |
| `clients` | Array of [`McpRegisteredClient`](mcpregisteredclient.md) | No | `[]` |
| `oauth_enabled` | `boolean` | Yes | Not specified |
| `oauth_registration` | `string` or `null` | Yes | Not specified |
| `supported_scopes` | Array of `string` | Yes | Not specified |
| `tools` | Array of [`McpToolCapability`](mcptoolcapability.md) | Yes | Not specified |
| `review` | [`McpReviewSupport`](mcpreviewsupport.md) | Yes | Not specified |
| `client_acceptance` | `string` | No | `"not_verified"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### transport

- Exact value: `"streamable-http"`

### authentication

- Each item: Allowed values: `"personal_token"`, `"oauth"`

### oauth_registration

- anyOf branch 1 (`string`): Exact value: `"pre_registered"`

### client_acceptance

- Exact value: `"not_verified"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "enabled": {
          "title": "Enabled",
          "type": "boolean"
        },
        "local_only": {
          "default": false,
          "title": "Local Only",
          "type": "boolean"
        },
        "endpoint": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Endpoint"
        },
        "transport": {
          "const": "streamable-http",
          "default": "streamable-http",
          "title": "Transport",
          "type": "string"
        },
        "authentication": {
          "items": {
            "enum": [
              "personal_token",
              "oauth"
            ],
            "type": "string"
          },
          "title": "Authentication",
          "type": "array"
        },
        "clients": {
          "default": [],
          "items": {
            "$ref": "#/$defs/McpRegisteredClient"
          },
          "title": "Clients",
          "type": "array"
        },
        "oauth_enabled": {
          "title": "Oauth Enabled",
          "type": "boolean"
        },
        "oauth_registration": {
          "anyOf": [
            {
              "const": "pre_registered",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Oauth Registration"
        },
        "supported_scopes": {
          "items": {
            "type": "string"
          },
          "title": "Supported Scopes",
          "type": "array"
        },
        "tools": {
          "items": {
            "$ref": "#/$defs/McpToolCapability"
          },
          "title": "Tools",
          "type": "array"
        },
        "review": {
          "$ref": "#/$defs/McpReviewSupport"
        },
        "client_acceptance": {
          "const": "not_verified",
          "default": "not_verified",
          "title": "Client Acceptance",
          "type": "string"
        }
      },
      "required": [
        "enabled",
        "endpoint",
        "authentication",
        "oauth_enabled",
        "oauth_registration",
        "supported_scopes",
        "tools",
        "review"
      ],
      "title": "McpConnectionDescriptor",
      "type": "object"
    }
    ```
