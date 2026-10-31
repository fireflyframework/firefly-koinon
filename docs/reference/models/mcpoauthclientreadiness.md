<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpOAuthClientReadiness

[All wire models](index.md)

Model aliases: `McpOAuthClientReadiness`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `ready` | `boolean` | Yes | Not specified |
| `endpoint_enabled` | `boolean` | Yes | Not specified |
| `oauth_enabled` | `boolean` | Yes | Not specified |
| `encryption_configured` | `boolean` | Yes | Not specified |
| `missing_configuration` | Array of `string` | Yes | Not specified |
| `static_clients_read_only` | `boolean` | No | `true` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### missing_configuration

- Each item: Allowed values: `"mcp_endpoint"`, `"oauth_enabled"`, `"oauth_encryption_key"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "ready": {
          "title": "Ready",
          "type": "boolean"
        },
        "endpoint_enabled": {
          "title": "Endpoint Enabled",
          "type": "boolean"
        },
        "oauth_enabled": {
          "title": "Oauth Enabled",
          "type": "boolean"
        },
        "encryption_configured": {
          "title": "Encryption Configured",
          "type": "boolean"
        },
        "missing_configuration": {
          "items": {
            "enum": [
              "mcp_endpoint",
              "oauth_enabled",
              "oauth_encryption_key"
            ],
            "type": "string"
          },
          "title": "Missing Configuration",
          "type": "array"
        },
        "static_clients_read_only": {
          "default": true,
          "title": "Static Clients Read Only",
          "type": "boolean"
        }
      },
      "required": [
        "ready",
        "endpoint_enabled",
        "oauth_enabled",
        "encryption_configured",
        "missing_configuration"
      ],
      "title": "McpOAuthClientReadiness",
      "type": "object"
    }
    ```
